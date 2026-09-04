import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client/dio_client.dart';

/// 流水线（Phase 5）：NovaFlow 模板列表 + 运行 + 自定义 YAML 保存。
class PipelinePage extends ConsumerStatefulWidget {
  const PipelinePage({super.key});

  @override
  ConsumerState<PipelinePage> createState() => _PipelinePageState();
}

class _PipelinePageState extends ConsumerState<PipelinePage> {
  List<dynamic> _pipelines = [];
  String? _error;
  final _yamlCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _yamlCtrl.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final items = await api.listPipelines();
      if (!mounted) return;
      setState(() {
        _pipelines = items;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _run(String name, String title) async {
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.runPipeline(name, title: '流水线: $title');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('✅ 流水线已启动 ${task['task_uuid']?.toString().substring(0, 8)}'),
      ));
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('❌ [${e.code}] ${e.message}')),
      );
    }
  }

  Future<void> _saveYaml() async {
    final api = ref.read(apiClientProvider);
    try {
      final parsed = await api.savePipeline(_yamlCtrl.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('✅ 模板 ${parsed['name']} 已保存（PostgreSQL）')),
      );
      _yamlCtrl.clear();
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
      return Center(child: Text('加载失败：$_error', style: const TextStyle(color: Colors.red)));
    }
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('流水线', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text('NovaFlow 编排引擎 · 模板持久化于 PostgreSQL',
            style: theme.textTheme.bodySmall),
        const SizedBox(height: 16),
        for (final pipeline in _pipelines)
          Card(
            child: ListTile(
              leading: Text(pipeline['is_builtin'] == true ? '🔧' : '⭐',
                  style: const TextStyle(fontSize: 20)),
              title: Text('${pipeline['title']}'),
              subtitle: Text(
                '${pipeline['name']} · ${pipeline['description']}\n'
                '${(pipeline['steps'] as List).length} 个步骤',
              ),
              isThreeLine: true,
              trailing: FilledButton.tonal(
                onPressed: () => _run(pipeline['name'], pipeline['title']),
                child: const Text('运行'),
              ),
            ),
          ),
        const SizedBox(height: 16),
        Text('保存自定义模板', style: theme.textTheme.titleMedium),
        const SizedBox(height: 8),
        TextField(
          controller: _yamlCtrl,
          maxLines: 8,
          decoration: const InputDecoration(
            hintText: 'name: my_pipeline\ntitle: 我的流水线\nsteps:\n  - name: 步骤一\n    task_type: mineru\n    module: mineru',
          ),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _saveYaml,
          icon: const Icon(Icons.save_outlined),
          label: const Text('保存模板'),
        ),
      ],
    );
  }
}
