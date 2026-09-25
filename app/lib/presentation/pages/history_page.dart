import 'dart:async';

import 'package:animations/animations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';
import '../widgets/context_actions.dart';
import '../widgets/undo_bar.dart';
import 'history_detail.dart';

/// 任务历史 · 星图志（方案 §5.4 / UX P0-2）：
/// - WS 消费（MF4 修复基线 bug③ 延续）：非终态任务订阅 /ws/logs/{uuid}，
///   status/progress 原位更新，终态关订阅；重连后 REST 全量刷新；
/// - 列表卡：星符徽标+标题+类型+耗时 mono+相对时刻；failed/canceled 流水线
///   任务副题「停于步骤 N/M」（/tasks/{uuid}/steps 惰性补拉，禁伪造）；
/// - 行 → 详情 Container Transform（#21，animations.OpenContainer 官方实现）；
/// - 任务级重试带 #16 撤销倒计时（10s 内可撤=取消新任务）；
/// - 右键菜单（重试/取消/导出日志/资源管理器中显示/复制 UUID）。
class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage>
    with WidgetsBindingObserver {
  static const _filters = <(String?, String)>[
    (null, '全部'),
    ('pending', '排队'),
    ('running', '运行中'),
    ('success', '成功'),
    ('failed', '失败'),
    ('canceled', '已取消'),
  ];

  static const _terminal = {'success', 'failed', 'canceled'};

  String? _status;
  List<Map<String, dynamic>> _tasks = [];
  final Map<String, (int, int)> _stopAt = {}; // uuid → (停于步骤 N, 总步数 M)
  String? _error;
  bool _loading = false;
  final Map<String, ForgeWebSocket> _subs = {};
  Timer? _reconnectDebounce;
  String? _undoingUuid; // 撤销倒计时中的新任务

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_refresh());
    ref.listenManual(taskEventsProvider, (previous, next) => _refresh());
    ref.listenManual(refreshEventsProvider, (previous, next) => _refresh());
    ref.listenManual(connectionProvider, (prev, next) {
      // WS 重连恢复 → REST 全量刷新（pro §2.4 断线策略）
      if (prev?.status == WsStatus.disconnected &&
          next.status == WsStatus.connected) {
        _reconnectDebounce?.cancel();
        _reconnectDebounce = Timer(const Duration(milliseconds: 500), () {
          unawaited(_refresh());
        });
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _reconnectDebounce?.cancel();
    for (final ws in _subs.values) {
      ws.dispose();
    }
    _subs.clear();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_loading) return;
    setState(() => _loading = true);
    final api = ref.read(apiClientProvider);
    try {
      final items = await api.listTasks(status: _status);
      if (!mounted) return;
      setState(() {
        _tasks = items.cast<Map<String, dynamic>>();
        _error = null;
        _loading = false;
      });
      _syncSubscriptions();
      unawaited(_fillStopAtSteps());
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  /// 「停于步骤 N/M」（UX P0-2）：失败/取消的流水线任务惰性补拉步骤明细。
  Future<void> _fillStopAtSteps() async {
    final api = ref.read(apiClientProvider);
    final targets = _tasks
        .where((t) =>
            t['mode'] == 'pipeline' &&
            (t['status'] == 'failed' || t['status'] == 'canceled'))
        .take(20)
        .toList();
    for (final task in targets) {
      final uuid = task['task_uuid'] as String?;
      if (uuid == null || _stopAt.containsKey(uuid)) continue;
      try {
        final data = await api.taskDetail(uuid);
        if (!mounted) return;
        final steps = (data['steps'] as List?) ?? const [];
        var stoppedAt = 0;
        for (final raw in steps) {
          final status = (raw as Map)['status'] as String?;
          if (status == 'success') stoppedAt += 1;
        }
        // 停于 = 最后一个非成功步骤位次（首个 failed/pending/running）
        var n = 0;
        for (var i = 0; i < steps.length; i++) {
          if (((steps[i] as Map)['status'] as String?) != 'success') {
            n = i + 1;
            break;
          }
        }
        if (n == 0 && stoppedAt > 0) n = stoppedAt + 1;
        setState(() => _stopAt[uuid] = (n, steps.length));
      } on ApiError {
        // 单个任务补拉失败不阻塞列表（无该副题=无数据，禁伪造）
      }
    }
  }

  /// 为非终态任务建 WS 订阅；终态任务关订阅（WS 消费核心）。
  void _syncSubscriptions() {
    final activeUuids = <String>{};
    for (final task in _tasks) {
      final uuid = task['task_uuid'] as String?;
      final status = task['status'] as String?;
      if (uuid == null) continue;
      if (status == 'pending' || status == 'running') {
        activeUuids.add(uuid);
        if (!_subs.containsKey(uuid)) _subscribe(uuid);
      }
    }
    for (final uuid in _subs.keys.toSet()) {
      if (!activeUuids.contains(uuid)) {
        _subs.remove(uuid)?.dispose();
      }
    }
  }

  void _subscribe(String uuid) {
    final ws = ForgeWebSocket(path: '/ws/logs/$uuid')
      ..messages.listen((envelope) => _onTaskEvent(uuid, envelope));
    ws.connect();
    _subs[uuid] = ws;
  }

  /// WS status/progress 事件原位更新（禁整页重拉——事件驱动）。
  void _onTaskEvent(String uuid, Map<String, dynamic> envelope) {
    final type = envelope['type'] as String?;
    if (type != 'status' && type != 'progress') return;
    final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>() ?? {};
    if (!mounted) return;
    setState(() {
      for (var i = 0; i < _tasks.length; i++) {
        if (_tasks[i]['task_uuid'] == uuid) {
          _tasks[i] = {
            ..._tasks[i],
            'status': payload['status'] as String? ?? _tasks[i]['status'],
            'progress': payload['progress'] ?? _tasks[i]['progress'],
            if (payload['error_code'] != null)
              'error_code': payload['error_code'],
          };
          final status = _tasks[i]['status'] as String?;
          if (status != null && _terminal.contains(status)) {
            _subs.remove(uuid)?.dispose(); // 终态关订阅
          }
          break;
        }
      }
    });
  }

  /// 任务级重试（新建同配置任务）+ #16 撤销倒计时（撤销=取消新任务）。
  Future<void> _retryWithUndo(String uuid) async {
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.retryTask(uuid);
      if (!mounted) return;
      ref.read(taskEventsProvider.notifier).taskMutated();
      setState(() => _undoingUuid = task['task_uuid'] as String?);
      unawaited(_refresh());
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  Future<void> _undoRetry() async {
    final api = ref.read(apiClientProvider);
    final newUuid = _undoingUuid;
    setState(() => _undoingUuid = null);
    if (newUuid == null) return;
    try {
      await api.cancelTask(newUuid);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('已撤销（新任务 ${newUuid.substring(0, 8)} 已取消）'),
      ));
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
    unawaited(_refresh());
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    if (_error != null) {
      return Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('加载失败：$_error',
              style: TextStyle(
                  fontSize: AstroType.body.size, color: palette.nova)),
          const SizedBox(height: 8),
          FilledButton.tonal(
            onPressed: _refresh,
            child: const Text('重试'),
          ),
        ]),
      );
    }
    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.all(AstroSpace.section),
          children: [
            Row(children: [
              Text('任务历史',
                  style: TextStyle(
                    fontSize: AstroType.h1.size,
                    fontWeight: AstroType.h1.weight,
                    color: palette.ink900,
                  )),
              const SizedBox(width: 12),
              Text(
                '星图志 · WS 实时（F5 刷新）',
                style:
                    TextStyle(fontSize: AstroType.caption.size, color: palette.ink400),
              ),
              if (_loading) ...[
                const SizedBox(width: 8),
                SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation(palette.aurora)),
                ),
              ],
            ]),
            const SizedBox(height: AstroSpace.gapLg),
            // 瞬时档：筛选 chips 即点即换（REST 查询 <100ms 禁骨架屏）
            FocusTraversalGroup(
              child: Wrap(
                spacing: 8,
                children: [
                  for (final (value, label) in _filters)
                    ChoiceChip(
                      label: Text(label),
                      selected: _status == value,
                      onSelected: (_) {
                        setState(() => _status = value);
                        _refresh();
                      },
                    ),
                ],
              ),
            ),
            const SizedBox(height: AstroSpace.gap),
            if (_tasks.isEmpty)
              _EmptyGuide(palette: palette, onGoTasks: () => _goTasks(context))
            else
              for (final task in _tasks)
                _TaskCard(
                  key: ValueKey(task['task_uuid']),
                  task: task,
                  stopAt: _stopAt[task['task_uuid'] as String? ?? ''],
                  palette: palette,
                  onRetry: () =>
                      _retryWithUndo(task['task_uuid'] as String),
                  onMutated: _refresh,
                ),
          ],
        ),
        // #16 撤销倒计时（页底悬浮）
        if (_undoingUuid != null)
          Positioned(
            left: AstroSpace.section,
            right: AstroSpace.section,
            bottom: AstroSpace.section,
            child: UndoCountdownBar(
              message:
                  '已重试为新任务 ${_undoingUuid!.substring(0, _undoingUuid!.length >= 8 ? 8 : _undoingUuid!.length)}',
              onUndo: _undoRetry,
              onDismissed: () => setState(() => _undoingUuid = null),
            ),
          ),
      ],
    );
  }

  void _goTasks(BuildContext context) {
    // 切到任务页（IA 8→5 后历史空态引导主落点）
    context.go('/tasks');
  }
}

// ---- 空态引导（空态矩阵：历史页引导）----

class _EmptyGuide extends StatelessWidget {
  const _EmptyGuide({required this.palette, required this.onGoTasks});

  final AstroPalette palette;
  final VoidCallback onGoTasks;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AstroSpace.empty),
      child: Center(
        child: Column(
          children: [
            Text(AstroIcons.navHistory,
                style: TextStyle(fontSize: 32, color: palette.ink400)),
            const SizedBox(height: AstroSpace.gap),
            Text('星图暂无航迹 —— 还没有任务记录',
                style: TextStyle(
                    fontSize: AstroType.titleSm.size, color: palette.ink900)),
            const SizedBox(height: 4),
            Text('从任务页发起，或回首页把文件拖进窗口',
                style: TextStyle(
                    fontSize: AstroType.bodySm.size, color: palette.ink400)),
            const SizedBox(height: AstroSpace.gapLg),
            FilledButton.tonal(
              onPressed: onGoTasks,
              child: const Text('去任务页'),
            ),
          ],
        ),
      ),
    );
  }
}

// ---- 历史卡（含 Container Transform 闭态）----

class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.task,
    required this.palette,
    required this.onRetry,
    required this.onMutated,
    this.stopAt,
    super.key,
  });

  final Map<String, dynamic> task;
  final AstroPalette palette;
  final VoidCallback onRetry;
  final VoidCallback onMutated;

  /// (停于步骤 N, 总步数 M)；null=无数据（非流水线/未补拉）。
  final (int, int)? stopAt;

  @override
  Widget build(BuildContext context) {
    final status = task['status'] as String? ?? 'pending';
    final uuid = task['task_uuid'] as String? ?? '';
    final outputDir = task['config']?['output_dir'] as String?;
    return GestureDetector(
      onSecondaryTapUp: (details) => showTaskContextMenu(
        context,
        position: details.globalPosition,
        taskUuid: uuid,
        status: status,
        outputDir: outputDir,
        onMutated: onMutated,
      ),
      child: OpenContainer<dynamic>(
        transitionDuration: const Duration(milliseconds: 300),
        transitionType: ContainerTransitionType.fadeThrough,
        closedElevation: 0,
        openElevation: 0,
        closedColor: palette.card,
        openColor: palette.bg,
        // 详情页弹回时带回「已变更」信号 → 列表刷新
        onClosed: (changed) {
          if (changed == true) onMutated();
        },
        closedBuilder: (context, open) => InkWell(
          onTap: open,
          child: Padding(
            padding: const EdgeInsets.symmetric(
                horizontal: AstroSpace.card, vertical: 12),
            child: _cardBody(context, palette, status, uuid),
          ),
        ),
        openBuilder: (context, _) => TaskDetailView(
          taskUuid: uuid,
          onChanged: () => onMutated(),
        ),
      ),
    );
  }

  Widget _cardBody(
      BuildContext context, AstroPalette palette, String status, String uuid) {
    final (glyph, color) = statusVisual(status, palette);
    final title = task['title'] as String? ?? '';
    final type = task['task_type'] as String? ?? '';
    final duration = _durationText();
    final created = _relativeTime(task['created_at'] as String?);
    final stop = stopAt;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            // 状态徽标 32 R999（色@12% wash + 星符）
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Center(
                child:
                    Text(glyph, style: TextStyle(fontSize: 13, color: color)),
              ),
            ),
            const SizedBox(width: AstroSpace.gapLg),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title.isNotEmpty ? title : '$type · ${_short(uuid)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: AstroType.titleSm.size,
                        fontWeight: FontWeight.w500,
                        color: palette.ink900),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    [
                      type,
                      if (task['mode'] == 'pipeline') '流水线',
                      // 停于步骤 N/M（UX P0-2：失败/取消流水线任务显式停点）
                      if (stop != null && stop.$2 > 0)
                        '停于步骤 ${stop.$1}/${stop.$2}',
                      if (duration != null) '耗时 $duration',
                      ?created,
                      if (task['error_code'] != null)
                        '错误 ${task['error_code']}',
                    ].where((s) => s.isNotEmpty).join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: AstroType.caption.size,
                        color: palette.ink600),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(AstroIcons.miscCaretRight,
                style: TextStyle(fontSize: 12, color: palette.ink400)),
          ],
        ),
      ],
    );
  }

  String _short(String uuid) => uuid.length >= 8 ? uuid.substring(0, 8) : uuid;

  String? _durationText() {
    final started = DateTime.tryParse(
        task['started_at'] as String? ?? '');
    final finished = DateTime.tryParse(
        task['finished_at'] as String? ?? '');
    if (started == null || finished == null) return null;
    final seconds = finished.difference(started).inSeconds;
    if (seconds < 60) return '${seconds}s';
    return '${seconds ~/ 60}m${(seconds % 60).toString().padLeft(2, '0')}s';
  }

  String? _relativeTime(String? iso) {
    final time = DateTime.tryParse(iso ?? '');
    if (time == null) return null;
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
    if (diff.inHours < 24) return '${diff.inHours} 小时前';
    return '${diff.inDays} 天前';
  }
}
