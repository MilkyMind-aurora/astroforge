import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';

/// 状态 → (星符, 色) 映射（历史页/任务页/详情共用口径）。
(String, Color) statusVisual(String status, AstroPalette palette) =>
    switch (status) {
      'success' => (AstroIcons.taskSuccess, palette.aurora),
      'failed' => (AstroIcons.taskFailed, palette.nova),
      'running' => (AstroIcons.taskRunning, palette.aurora),
      'canceled' => (AstroIcons.taskCanceled, palette.ink400),
      _ => (AstroIcons.taskPending, palette.ink600),
    };

/// 密集行右键菜单体系（UX P1：任务/产物/产物目录行——
/// 重试/取消/导出日志/资源管理器中显示/复制 UUID）。
/// 「资源管理器中显示」与「复制 UUID」为纯客户端能力；重试/取消/导出日志
/// 走服务 API（导出=REST 补拉全量后本地落盘）。
Future<void> showTaskContextMenu(
  BuildContext context, {
  required Offset position,
  required String taskUuid,
  required String? status,
  String? outputDir,
  VoidCallback? onMutated,
}) async {
  final palette = AstroPaletteScope.of(context);
  final canRetry = status == 'failed' || status == 'canceled';
  final canCancel = status == 'pending' || status == 'running';
  final overlay =
      Overlay.of(context).context.findRenderObject() as RenderBox?;
  if (overlay == null) return;
  final choice = await showMenu<String>(
    context: context,
    position: RelativeRect.fromLTRB(
      position.dx, position.dy, overlay.size.width - position.dx, 0,
    ),
    color: palette.cardRaised,
    shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AstroRadius.sm)),
    items: [
      if (canRetry)
        const PopupMenuItem(value: 'retry', height: 36, child: Text('重试（新建同配置任务）')),
      if (canCancel)
        const PopupMenuItem(value: 'cancel', height: 36, child: Text('取消任务')),
      if (outputDir != null && outputDir.isNotEmpty)
        const PopupMenuItem(value: 'reveal', height: 36, child: Text('在资源管理器中显示')),
      const PopupMenuItem(value: 'export', height: 36, child: Text('导出日志')),
      const PopupMenuItem(value: 'copy', height: 36, child: Text('复制 UUID')),
    ],
  );
  if (choice == null || !context.mounted) return;
  final api = ProviderScope.containerOf(context).read(apiClientProvider);
  switch (choice) {
    case 'retry':
      try {
        final task = await api.retryTask(taskUuid);
        if (!context.mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
              '${AstroIcons.taskSuccess} 已重试为新任务 ${(task['task_uuid'] as String?)?.substring(0, 8) ?? ''}'),
        ));
        onMutated?.call();
      } on ApiError catch (e) {
        _errorBar(context, '[${e.code}] ${e.message}');
      }
    case 'cancel':
      try {
        await api.cancelTask(taskUuid);
        if (!context.mounted) return;
        onMutated?.call();
      } on ApiError catch (e) {
        _errorBar(context, '[${e.code}] ${e.message}');
      }
    case 'reveal':
      await revealInFileManager(outputDir ?? '');
    case 'export':
      await exportTaskLogs(context, taskUuid);
    case 'copy':
      await Clipboard.setData(ClipboardData(text: taskUuid));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('UUID 已复制')),
        );
      }
  }
}

void _errorBar(BuildContext context, String message) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    content: Text('${AstroIcons.statusError} $message'),
  ));
}

/// 资源管理器中显示（Windows explorer /select；macOS open -R）。
/// 路径不存在时打开最近存在的祖先目录（禁伪造「已打开」）。
Future<void> revealInFileManager(String path) async {
  if (path.isEmpty) return;
  var target = path;
  var p = File(target);
  var isFile = p.existsSync();
  if (!isFile) {
    final dir = Directory(target);
    isFile = false;
    if (!dir.existsSync()) {
      // 逐级回退最近存在祖先
      var current = Directory(target);
      Directory? found;
      while (true) {
        final parent = current.parent;
        if (parent.path == current.path) break;
        if (parent.existsSync()) {
          found = parent;
          break;
        }
        current = parent;
      }
      target = found?.path ?? '';
      if (target.isEmpty) return;
    }
  }
  if (Platform.isWindows) {
    if (isFile) {
      await Process.run('explorer.exe', ['/select,', target]);
    } else {
      await Process.run('explorer.exe', [target]);
    }
  } else if (Platform.isMacOS) {
    await Process.run('open', ['-R', target]);
  } else {
    await Process.run('xdg-open', [target]);
  }
}

/// 导出任务日志：REST 全量补拉 → 系统保存对话框落盘。
Future<void> exportTaskLogs(BuildContext context, String taskUuid) async {
  final api = ProviderScope.containerOf(context).read(apiClientProvider);
  try {
    final lines = <String>[];
    var offset = 0;
    while (true) {
      final data = await api.taskLogs(taskUuid, offset: offset);
      final batch = (data['lines'] as List?) ?? const [];
      lines.addAll(batch.map((e) => e.toString()));
      final next = (data['offset'] as num?)?.toInt() ?? offset;
      if (batch.isEmpty || next <= offset) break;
      offset = next;
    }
    final bytes = utf8.encode(lines.join('\n'));
    final uri = await FilePicker.saveFile(
      fileName: 'astroforge-${taskUuid.substring(0, 8)}.log',
      bytes: bytes,
    );
    if (uri == null) return; // 用户取消
    // file_picker 12 saveFile 只回目标 Uri，落盘由调用方负责
    if (uri.scheme == 'file') {
      File(uri.toFilePath()).writeAsBytesSync(bytes);
    }
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('日志已导出（${lines.length} 行）')),
      );
    }
  } on ApiError catch (e) {
    if (!context.mounted) return;
    _errorBar(context, '[${e.code}] ${e.message}');
  }
}
