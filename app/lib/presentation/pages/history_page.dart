import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';

/// 任务历史 · 星图志（方案 §5.4 骨架，MF4 换脸）。
///
/// 修复基线 bug③：5s Timer 轮询 → WS 消费。
/// 数据策略（与服务核心已实现契约对齐——全局任务列表无 WS 通道，服务端仅按
/// 任务广播，与 TUI MF2 同一约束，见 tui/tui/plugins/history/page.py）：
/// - REST 首载 + 显式刷新（筛选切换 / F5 / 窗口重新聚焦 / 应用内任务变更事件）；
/// - 每个已知非终态任务订阅 /ws/logs/{uuid}，status/progress 事件实时原位
///   更新卡片（终态即关订阅）；重连成功后 REST 全量刷新补状态。
/// 已知边界（如实说明）：其他客户端新建的任务在本页无事件源，需 F5/聚焦刷新。
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
  String? _error;
  bool _loading = false;
  final Map<String, ForgeWebSocket> _subs = {};
  Timer? _reconnectDebounce;

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
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
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

  Future<void> _retry(String uuid) async {
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.retryTask(uuid);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('✓ 已重试为新任务 ${_short(task['task_uuid'] as String? ?? '')}'),
      ));
      await _refresh();
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
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('加载失败：$_error',
              style: TextStyle(fontSize: AstroType.body.size, color: palette.nova)),
          const SizedBox(height: 8),
          FilledButton.tonal(
            onPressed: _refresh,
            child: const Text('重试'),
          ),
        ]),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(24),
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
            style: TextStyle(fontSize: AstroType.caption.size, color: palette.ink400),
          ),
          if (_loading) ...[
            const SizedBox(width: 8),
            SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                  strokeWidth: 2, valueColor: AlwaysStoppedAnimation(palette.aurora)),
            ),
          ],
        ]),
        const SizedBox(height: AstroSpace.gapLg),
        Wrap(
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
        const SizedBox(height: AstroSpace.gap),
        for (final task in _tasks)
          _TaskCard(
            task: task,
            palette: palette,
            onRetry: () => _retry(task['task_uuid'] as String),
          ),
        if (_tasks.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AstroSpace.empty),
            child: Center(
              child: Text('暂无任务记录',
                  style: TextStyle(
                      fontSize: AstroType.bodySm.size, color: palette.ink400)),
            ),
          ),
      ],
    );
  }

  String _short(String uuid) => uuid.length >= 8 ? uuid.substring(0, 8) : uuid;
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.task,
    required this.palette,
    required this.onRetry,
  });

  final Map<String, dynamic> task;
  final AstroPalette palette;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final status = task['status'] as String? ?? 'pending';
    final (glyph, color) = switch (status) {
      'success' => (AstroIcons.taskSuccess, palette.aurora),
      'failed' => (AstroIcons.taskFailed, palette.nova),
      'running' => (AstroIcons.taskRunning, palette.aurora),
      'canceled' => (AstroIcons.taskCanceled, palette.ink400),
      _ => (AstroIcons.taskPending, palette.ink600),
    };
    final uuid = task['task_uuid'] as String? ?? '';
    final short = uuid.length >= 8 ? uuid.substring(0, 8) : uuid;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Text(glyph, style: TextStyle(color: color, fontSize: 18)),
        title: Text(
          '$short · ${task['task_type']}'
          '${task['mode'] == 'pipeline' ? '  流水线' : ''}',
          style: TextStyle(fontSize: AstroType.titleSm.size, color: palette.ink900),
        ),
        subtitle: Text(
          '${task['title'] ?? ''}  进度 ${task['progress']}%'
          '${task['error_code'] != null ? '  错误 ${task['error_code']}' : ''}',
          style: TextStyle(fontSize: AstroType.caption.size, color: palette.ink600),
        ),
        trailing: (status == 'failed' || status == 'canceled')
            ? TextButton(
                onPressed: onRetry,
                child: Text('重试', style: TextStyle(color: palette.auroraText)),
              )
            : Text(status,
                style:
                    TextStyle(fontSize: AstroType.caption.size, color: palette.ink400)),
      ),
    );
  }
}
