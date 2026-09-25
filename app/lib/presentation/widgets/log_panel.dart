import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';

/// 全局日志面板（Ctrl+`；TUI 同名映射）：底部 60% 高抽屉。
/// 任务切换器（运行中 > 最近失败 > 最近成功）+ 级别过滤 chips +
/// WS 流式增量 + REST 断线补拉（GET /tasks/{uuid}/logs）。
class LogPanel extends ConsumerStatefulWidget {
  const LogPanel({required this.onClose, super.key});

  final VoidCallback onClose;

  static Future<void> show(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return showDialog<void>(
      context: context,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      barrierLabel: '日志面板',
      builder: (dialogContext) => Align(
        alignment: Alignment.bottomCenter,
        child: Padding(
          padding: const EdgeInsets.all(AstroSpace.section),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: 860,
              maxHeight: MediaQuery.sizeOf(context).height * 0.6,
            ),
            child: LogPanel(onClose: () => Navigator.of(dialogContext).pop()),
          ),
        ),
      ),
    );
  }

  @override
  ConsumerState<LogPanel> createState() => _LogPanelState();
}

class _LogPanelState extends ConsumerState<LogPanel> {
  List<Map<String, dynamic>> _candidates = [];
  String? _selectedUuid;
  final List<(String, String)> _lines = []; // (level, text)
  final Set<String> _levels = {'INFO', 'WARN', 'ERROR'};
  bool _loadingTasks = true;
  String? _error;
  ForgeWebSocket? _ws;

  @override
  void initState() {
    super.initState();
    _loadCandidates();
  }

  @override
  void dispose() {
    _ws?.dispose();
    super.dispose();
  }

  /// 任务切换器排序：运行中 > 最近失败 > 最近成功 > 其他。
  Future<void> _loadCandidates() async {
    try {
      final items = await ref.read(apiClientProvider).listTasks();
      if (!mounted) return;
      final tasks = items.cast<Map<String, dynamic>>();
      int rank(String? status) => switch (status) {
            'running' || 'pending' => 0,
            'failed' => 1,
            'success' => 2,
            _ => 3,
          };
      tasks.sort((a, b) =>
          rank(a['status'] as String?).compareTo(rank(b['status'] as String?)));
      setState(() {
        _candidates = tasks;
        _loadingTasks = false;
      });
      final first = tasks.firstOrNull?['task_uuid'] as String?;
      if (first != null) _select(first);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingTasks = false;
        _error = '[${e.code}] ${e.message}';
      });
    }
  }

  void _select(String uuid) {
    _ws?.dispose();
    setState(() {
      _selectedUuid = uuid;
      _lines.clear();
    });
    // REST 补拉尾 50 行（断线兜底），再开 WS 增量
    _pullRest(uuid);
    _ws = ForgeWebSocket(path: '/ws/logs/$uuid')
      ..messages.listen((envelope) {
        if (envelope['type'] != 'log') return;
        final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>();
        if (payload == null || !mounted) return;
        setState(() {
          _lines.add((
            (payload['level'] as String?) ?? 'INFO',
            (payload['text'] as String?) ?? ''
          ));
          if (_lines.length > 500) _lines.removeRange(0, _lines.length - 500);
        });
      })
      ..connect();
  }

  Future<void> _pullRest(String uuid) async {
    try {
      final data = await ref.read(apiClientProvider).taskLogs(uuid, offset: 0);
      if (!mounted) return;
      final lines = ((data['lines'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
      if (lines.isEmpty) return;
      setState(() {
        for (final line in lines) {
          // REST 行已带级别前缀格式 [INFO] …（stdout 契约）
          final level = line.startsWith('[ERROR]')
              ? 'ERROR'
              : line.startsWith('[WARN]')
                  ? 'WARN'
                  : 'INFO';
          _lines.add((level, line));
        }
        if (_lines.length > 500) _lines.removeRange(0, _lines.length - 500);
      });
    } on ApiError {
      // 无日志留 WS 增量
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final visible = _lines
        .where((line) => _levels.contains(line.$1))
        .toList()
        .reversed
        .take(300)
        .toList()
        .reversed
        .toList();
    return Material(
      color: palette.cardRaised,
      borderRadius: BorderRadius.circular(AstroRadius.lg),
      child: Container(
        height: MediaQuery.sizeOf(context).height * 0.6,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AstroRadius.lg),
          border: Border.all(color: palette.stroke),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ---- 头部：任务切换器 + 级别过滤 ----
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                children: [
                  Text('日志',
                      style: TextStyle(
                          fontSize: AstroType.titleSm.size,
                          fontWeight: FontWeight.w600,
                          color: palette.ink900)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _loadingTasks
                        ? Text('读取任务列表…',
                            style: TextStyle(
                                fontSize: AstroType.caption.size,
                                color: palette.ink400))
                        : DropdownButton<String>(
                            value: _selectedUuid,
                            isDense: true,
                            underline: const SizedBox.shrink(),
                            style: TextStyle(
                                fontSize: AstroType.caption.size,
                                color: palette.ink900),
                            dropdownColor: palette.cardRaised,
                            items: [
                              for (final task in _candidates.take(20))
                                DropdownMenuItem(
                                  value: task['task_uuid'] as String?,
                                  child: Text(
                                    '${(task['task_uuid'] as String).substring(0, 8)} · '
                                    '${task['task_type']} · ${task['status']}',
                                  ),
                                ),
                            ],
                            onChanged: (uuid) {
                              if (uuid != null) _select(uuid);
                            },
                          ),
                  ),
                  for (final level in const ['INFO', 'WARN', 'ERROR'])
                    Padding(
                      padding: const EdgeInsets.only(left: 4),
                      child: FilterChip(
                        label: Text(level,
                            style: TextStyle(fontSize: AstroType.label.size)),
                        selected: _levels.contains(level),
                        onSelected: (on) => setState(() {
                          on ? _levels.add(level) : _levels.remove(level);
                        }),
                      ),
                    ),
                  IconButton(
                    tooltip: '关闭（Esc / Ctrl+`）',
                    onPressed: widget.onClose,
                    icon: Icon(LucideIcons.x, size: 16, color: palette.ink600),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            // ---- 日志流（mono，禁逐帧整块重排——WS 增量 append 行级）----
            Expanded(
              child: _error != null
                  ? Center(
                      child: Text('加载失败：$_error',
                          style: TextStyle(
                              fontSize: AstroType.bodySm.size,
                              color: palette.nova)))
                  : _selectedUuid == null
                      ? Center(
                          child: Text('暂无任务可选',
                              style: TextStyle(
                                  fontSize: AstroType.bodySm.size,
                                  color: palette.ink400)))
                      : SingleChildScrollView(
                          reverse: true,
                          padding: const EdgeInsets.all(12),
                          child: visible.isEmpty
                              ? Text('暂无日志 —— 任务启动后逐行滚动',
                                  style: TextStyle(
                                      fontFamily: AstroType.monoFamily,
                                      fontSize: AstroType.caption.size,
                                      color: palette.ink400))
                              : Text.rich(
                                  TextSpan(
                                    children: [
                                      for (final (level, text) in visible)
                                        TextSpan(
                                          text: '$text\n',
                                          style: TextStyle(
                                            fontFamily:
                                                AstroType.monoFamily,
                                            fontSize:
                                                AstroType.caption.size,
                                            height: 1.5,
                                            color: level == 'ERROR'
                                                ? palette.nova
                                                : level == 'WARN'
                                                    ? palette.molten
                                                    : palette.ink600,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
