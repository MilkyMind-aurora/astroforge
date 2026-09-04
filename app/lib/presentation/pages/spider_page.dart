import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client/dio_client.dart';

/// 采集中心（Phase 2）：四类爬取任务表单 + 最近任务。
class SpiderPage extends ConsumerStatefulWidget {
  const SpiderPage({super.key});

  @override
  ConsumerState<SpiderPage> createState() => _SpiderPageState();
}

class _SpiderPageState extends ConsumerState<SpiderPage> {
  static const _types = <(String, String, String)>[
    ('spider_single', '单页转 MD', '渲染单个网页并提取正文为 Markdown'),
    ('spider_site', '整站结构化', '解析侧边栏目录，按章节输出 Markdown 树'),
    ('spider_pdf', 'PDF 批量下载', '抓取页面上的全部 PDF 链接并下载'),
    ('spider_table', '表格抓取', '批量抓取公开数据表格（Phase 2 开发中）'),
  ];

  String _selected = 'spider_single';
  final _urlCtrl = TextEditingController();
  final _outputCtrl = TextEditingController();
  final _maxPagesCtrl = TextEditingController(text: '200');
  final _intervalCtrl = TextEditingController(text: '1.0');
  String? _result;
  bool _busy = false;
  List<dynamic> _recent = [];

  @override
  void initState() {
    super.initState();
    _refreshRecent();
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    _outputCtrl.dispose();
    _maxPagesCtrl.dispose();
    _intervalCtrl.dispose();
    super.dispose();
  }

  Future<void> _refreshRecent() async {
    final api = ref.read(apiClientProvider);
    try {
      final items = await api.listTasks();
      if (!mounted) return;
      setState(() => _recent = items.take(5).toList());
    } on ApiError {
      // 列表失败不打断表单操作
    }
  }

  Future<void> _submit() async {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) {
      setState(() => _result = '❌ URL 必填');
      return;
    }
    setState(() {
      _busy = true;
      _result = null;
    });
    final config = <String, dynamic>{'url': url};
    if (_outputCtrl.text.trim().isNotEmpty) {
      config['output_dir'] = _outputCtrl.text.trim();
    }
    if (_selected == 'spider_site' && _maxPagesCtrl.text.trim().isNotEmpty) {
      config['max_pages'] = int.tryParse(_maxPagesCtrl.text.trim()) ?? 200;
    }
    if (_intervalCtrl.text.trim().isNotEmpty) {
      config['request_interval'] = double.tryParse(_intervalCtrl.text.trim()) ?? 1.0;
    }
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.createTask(_selected, config);
      if (!mounted) return;
      setState(() {
        _result = '✅ 任务 ${task['task_uuid']?.toString().substring(0, 8)} 已创建（${task['status']}）';
      });
      await _refreshRecent();
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _result = '❌ [${e.code}] ${e.message}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('采集中心', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text('Scrapling 自适应爬虫 · 本地 Chromium 渲染',
            style: theme.textTheme.bodySmall),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          children: [
            for (final (key, label, _) in _types)
              ChoiceChip(
                label: Text(label),
                selected: _selected == key,
                onSelected: (_) => setState(() => _selected = key),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Text(_types.firstWhere((t) => t.$1 == _selected).$3,
            style: theme.textTheme.bodySmall),
        const SizedBox(height: 12),
        TextField(
          controller: _urlCtrl,
          decoration: const InputDecoration(
            labelText: '目标 URL *',
            hintText: 'https://cn.vuejs.org/guide/introduction.html',
          ),
        ),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _outputCtrl,
              decoration: const InputDecoration(labelText: '输出目录（可选）'),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 120,
            child: TextField(
              controller: _intervalCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '间隔(秒)'),
            ),
          ),
        ]),
        if (_selected == 'spider_site') ...[
          const SizedBox(height: 8),
          SizedBox(
            width: 160,
            child: TextField(
              controller: _maxPagesCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '最大页面数'),
            ),
          ),
        ],
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _busy ? null : _submit,
          icon: _busy
              ? const SizedBox(width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.rocket_launch_outlined),
          label: Text(_busy ? '提交中…' : '启动任务'),
        ),
        if (_result != null) ...[
          const SizedBox(height: 12),
          Text(_result!),
        ],
        const SizedBox(height: 24),
        Row(children: [
          Text('最近任务', style: theme.textTheme.titleMedium),
          IconButton(
            onPressed: _refreshRecent,
            icon: const Icon(Icons.refresh, size: 20),
          ),
        ]),
        for (final task in _recent)
          ListTile(
            dense: true,
            leading: Icon(
              switch (task['status']) {
                'success' => Icons.check_circle,
                'failed' => Icons.error,
                'running' => Icons.autorenew,
                _ => Icons.schedule,
              },
              size: 20,
            ),
            title: Text('${task['task_uuid']?.toString().substring(0, 8)} · ${task['task_type']}'),
            subtitle: Text('进度 ${task['progress']}%'),
            trailing: Text('${task['status']}',
                style: theme.textTheme.bodySmall),
          ),
      ],
    );
  }
}
