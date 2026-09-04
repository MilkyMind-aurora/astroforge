import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client/dio_client.dart';

/// 任务历史（Phase 1.4）：状态筛选 + 5s 自动刷新，数据来自 PostgreSQL。
class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  static const _filters = <(String?, String)>[
    (null, '全部'),
    ('pending', '排队'),
    ('running', '运行中'),
    ('success', '成功'),
    ('failed', '失败'),
    ('canceled', '已取消'),
  ];

  String? _status;
  List<dynamic> _tasks = [];
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final items = await api.listTasks(status: _status);
      if (!mounted) return;
      setState(() {
        _tasks = items;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _retry(String uuid) async {
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.retryTask(uuid);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('✅ 已重试为新任务 ${task['task_uuid']?.toString().substring(0, 8)}'),
      ));
      await _refresh();
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('❌ [${e.code}] ${e.message}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_error != null) {
      return Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('加载失败：$_error', style: const TextStyle(color: Colors.red)),
          FilledButton.tonal(onPressed: _refresh, child: const Text('重试')),
        ]),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Row(children: [
          Text('任务历史', style: theme.textTheme.headlineSmall),
          const SizedBox(width: 8),
          const Icon(Icons.sync, size: 14),
          Text(' 5s 自动刷新', style: theme.textTheme.bodySmall),
        ]),
        const SizedBox(height: 12),
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
        const SizedBox(height: 8),
        for (final task in _tasks)
          Card(
            child: ListTile(
              leading: Icon(
                switch (task['status']) {
                  'success' => Icons.check_circle,
                  'failed' => Icons.error,
                  'running' => Icons.autorenew,
                  'canceled' => Icons.cancel_outlined,
                  _ => Icons.schedule,
                },
                color: switch (task['status']) {
                  'success' => Colors.green,
                  'failed' => theme.colorScheme.error,
                  'running' => Colors.orange,
                  _ => Colors.grey,
                },
              ),
              title: Text(
                '${task['task_uuid']?.toString().substring(0, 8)} · ${task['task_type']}'
                '  ${task['mode'] == 'pipeline' ? '⛓ 流水线' : ''}',
              ),
              subtitle: Text(
                '${task['title'] ?? ''}  进度 ${task['progress']}%'
                '${task['error_code'] != null ? '  错误 ${task['error_code']}' : ''}',
              ),
              trailing: (task['status'] == 'failed' || task['status'] == 'canceled')
                  ? TextButton(
                      onPressed: () => _retry(task['task_uuid']),
                      child: const Text('重试'),
                    )
                  : Text('${task['status']}', style: theme.textTheme.bodySmall),
            ),
          ),
        if (_tasks.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 32),
            child: Center(child: Text('暂无任务记录', style: theme.textTheme.bodySmall)),
          ),
      ],
    );
  }
}
