import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';
import '../widgets/context_actions.dart';
import '../widgets/step_timeline.dart';

/// 任务详情（历史行 Container Transform 的展开态，方案 §5.4）：
/// 头部（状态徽标+标题+UUID mono+相对时刻+真实进度条）→ 步骤时间线
/// （失败步骤内联「从步骤 N 继续」接 MF3.5 API）→ 产物目录行
/// （config.output_dir 真实值 + 资源管理器中显示/复制路径）→
/// 日志（WS 实时 + REST 断线补拉尾 20 行）→ 操作行（重试/取消/导出日志）。
class TaskDetailView extends ConsumerStatefulWidget {
  const TaskDetailView({required this.taskUuid, this.onChanged, super.key});

  final String taskUuid;

  /// 任务变更（重试/续跑/取消）后回调列表层刷新（Container Transform 收口）。
  final VoidCallback? onChanged;

  @override
  ConsumerState<TaskDetailView> createState() => _TaskDetailViewState();
}

class _TaskDetailViewState extends ConsumerState<TaskDetailView> {
  Map<String, dynamic>? _task;
  String? _error;
  final List<String> _logTail = [];
  ForgeWebSocket? _logWs;

  @override
  void initState() {
    super.initState();
    _load();
    _subscribeLogs();
  }

  @override
  void dispose() {
    _logWs?.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final detail = await ref.read(apiClientProvider).taskDetail(widget.taskUuid);
      if (!mounted) return;
      setState(() => _task = detail);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = '[${e.code}] ${e.message}');
    }
  }

  void _subscribeLogs() {
    _logWs?.dispose();
    final ws = ForgeWebSocket(path: '/ws/logs/${widget.taskUuid}')
      ..messages.listen((envelope) {
        final type = envelope['type'] as String?;
        final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>();
        if (type == 'log' && payload != null && mounted) {
          setState(() {
            _logTail.add('[${payload['level']}] ${payload['text']}');
            if (_logTail.length > 200) {
              _logTail.removeRange(0, _logTail.length - 200);
            }
          });
        }
        // status 事件驱动详情刷新（续跑原地更新——uuid 不变）
        if (type == 'status') unawaited(_load());
      });
    // 断线 REST 补拉兜底：先拉尾 20 行，WS 只做增量
    ws.connect();
    _logWs = ws;
    _pullRestTail();
  }

  Future<void> _pullRestTail() async {
    try {
      final data =
          await ref.read(apiClientProvider).taskLogs(widget.taskUuid, offset: 0);
      if (!mounted) return;
      final lines = ((data['lines'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
      if (lines.isEmpty) return;
      setState(() {
        _logTail
          ..clear()
          ..addAll(lines.length > 20 ? lines.sublist(lines.length - 20) : lines);
      });
    } on ApiError {
      // 无日志/不可达：留 WS 增量（禁伪造空态文案以外的内容）
    }
  }

  Future<void> _taskRetry() async {
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.retryTask(widget.taskUuid);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
            '${AstroIcons.taskSuccess} 已重试为新任务 ${(task['task_uuid'] as String?)?.substring(0, 8)}'),
      ));
      widget.onChanged?.call();
      unawaited(_load());
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  Future<void> _taskCancel() async {
    final api = ref.read(apiClientProvider);
    try {
      await api.cancelTask(widget.taskUuid);
      if (!mounted) return;
      widget.onChanged?.call();
      unawaited(_load());
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    if (_error != null) {
      return Center(
        child: Text('加载失败：$_error',
            style: TextStyle(fontSize: AstroType.body.size, color: palette.nova)),
      );
    }
    final task = _task;
    if (task == null) {
      // 短时档：局部加载，无骨架屏（详情页体积小，瞬时到达）
      return const Center(child: SizedBox.shrink());
    }
    final status = task['status'] as String? ?? 'pending';
    final (glyph, color) = statusVisual(status, palette);
    final config = (task['config'] as Map?)?.cast<String, dynamic>() ?? const {};
    final outputDir = config['output_dir'] as String?;
    final steps = (task['steps'] as List?) ?? const [];
    final canRetry = status == 'failed' || status == 'canceled';
    final canCancel = status == 'pending' || status == 'running';

    return ListView(
      padding: const EdgeInsets.all(AstroSpace.section),
      children: [
        // ---- 头部 ----
        Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Center(
                  child:
                      Text(glyph, style: TextStyle(fontSize: 13, color: color))),
            ),
            const SizedBox(width: AstroSpace.gapLg),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (task['title'] as String?)?.isNotEmpty == true
                        ? task['title'] as String
                        : task['task_type'] as String? ?? '',
                    style: TextStyle(
                        fontSize: AstroType.h2.size,
                        fontWeight: AstroType.h2.weight,
                        color: palette.ink900),
                  ),
                  Text(
                    '${widget.taskUuid} · ${task['task_type']} · $status',
                    style: TextStyle(
                      fontFamily: AstroType.monoFamily,
                      fontSize: AstroType.caption.size,
                      color: palette.ink400,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: AstroSpace.gap),
        // 真实进度条（progress 字段；禁伪造）
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: ((task['progress'] as num?)?.toDouble() ?? 0) / 100,
            minHeight: 3,
            backgroundColor: palette.container,
            valueColor: AlwaysStoppedAnimation(palette.aurora),
          ),
        ),
        if (task['error_message'] != null) ...[
          const SizedBox(height: AstroSpace.gap),
          Text('${task['error_code'] ?? ''} ${task['error_message']}',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.nova)),
        ],

        // ---- 操作行（FocusTraversalGroup）----
        const SizedBox(height: AstroSpace.section),
        FocusTraversalGroup(
          child: Wrap(
            spacing: AstroSpace.gap,
            children: [
              if (canRetry)
                FilledButton.tonal(
                  onPressed: _taskRetry,
                  child: const Text('重试（新建同配置任务）'),
                ),
              if (canCancel)
                OutlinedButton(
                  onPressed: _taskCancel,
                  child: const Text('取消任务'),
                ),
              OutlinedButton(
                onPressed: () =>
                    exportTaskLogs(context, widget.taskUuid),
                child: const Text('导出日志'),
              ),
            ],
          ),
        ),

        // ---- 步骤时间线 ----
        const SizedBox(height: AstroSpace.sectionLg),
        Text('步骤',
            style: TextStyle(
                fontSize: AstroType.title.size,
                fontWeight: AstroType.title.weight,
                color: palette.ink900)),
        const SizedBox(height: AstroSpace.gap),
        if (steps.isEmpty)
          Text('（单步任务）',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.ink400))
        else
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AstroSpace.card),
              child: StepTimeline(
                steps: steps,
                taskUuid: widget.taskUuid,
                onStepRetried: (_) {
                  widget.onChanged?.call();
                  unawaited(_load());
                },
              ),
            ),
          ),

        // ---- 产物目录 ----
        if (outputDir != null && outputDir.isNotEmpty) ...[
          const SizedBox(height: AstroSpace.sectionLg),
          Text('产物',
              style: TextStyle(
                  fontSize: AstroType.title.size,
                  fontWeight: AstroType.title.weight,
                  color: palette.ink900)),
          const SizedBox(height: AstroSpace.gap),
          // 产物行右键语义（资源管理器中显示）；产物索引 API 未建（服务端仅
          // artifacts 表，无路由）——以 config.output_dir 真实值为准，禁伪造清单
          Card(
            child: ListTile(
              leading: Text(AstroIcons.miscStarMid,
                  style: TextStyle(color: palette.ink600, fontSize: 14)),
              title: Text(outputDir,
                  style: TextStyle(
                      fontFamily: AstroType.monoFamily,
                      fontSize: AstroType.bodySm.size,
                      color: palette.ink900)),
              subtitle: Text('输出目录（config.output_dir）',
                  style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink400)),
              trailing: Wrap(spacing: 4, children: [
                IconButton(
                  tooltip: '在资源管理器中显示',
                  icon: const Icon(Icons.folder_open_outlined, size: 18),
                  onPressed: () => revealInFileManager(outputDir),
                ),
                IconButton(
                  tooltip: '复制路径',
                  icon: const Icon(Icons.copy_outlined, size: 18),
                  onPressed: () => _copyPath(context, outputDir),
                ),
              ]),
            ),
          ),
        ],

        // ---- 日志 ----
        const SizedBox(height: AstroSpace.sectionLg),
        Text('日志（WS 实时 + REST 补拉）',
            style: TextStyle(
                fontSize: AstroType.title.size,
                fontWeight: AstroType.title.weight,
                color: palette.ink900)),
        const SizedBox(height: AstroSpace.gap),
        Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxHeight: 220),
          padding: const EdgeInsets.all(AstroSpace.card),
          decoration: BoxDecoration(
            color: palette.sunken,
            borderRadius: BorderRadius.circular(AstroRadius.sm),
          ),
          child: SingleChildScrollView(
            reverse: true,
            child: _logTail.isEmpty
                ? Text('暂无日志 —— 任务启动后逐行滚动（Ctrl+` 打开全局日志面板）',
                    style: TextStyle(
                        fontSize: AstroType.caption.size,
                        color: palette.ink400))
                : Text(
                    _logTail.join('\n'),
                    style: TextStyle(
                      fontFamily: AstroType.monoFamily,
                      fontSize: AstroType.caption.size,
                      height: 1.5,
                      color: palette.ink600,
                    ),
                  ),
          ),
        ),
      ],
    );
  }

  void _copyPath(BuildContext context, String path) {
    Clipboard.setData(ClipboardData(text: path));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('路径已复制')),
    );
  }
}
