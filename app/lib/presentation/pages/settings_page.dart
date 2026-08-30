import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client/dio_client.dart';

/// 设置页（Phase 1.3.3）：配置摘要 + 覆盖设置编辑 + token 重置。
class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  Map<String, dynamic>? _summary;
  final _warningCtrl = TextEditingController();
  final _criticalCtrl = TextEditingController();
  final _intervalCtrl = TextEditingController();
  final _templateCtrl = TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _warningCtrl.dispose();
    _criticalCtrl.dispose();
    _intervalCtrl.dispose();
    _templateCtrl.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final summary = await api.configSummary();
      final overrides = await api.listAppSettings();
      if (!mounted) return;
      final monitor = (summary['monitor'] ?? {}) as Map<String, dynamic>;
      _warningCtrl.text = '${overrides['memory_warning_gb']?['value'] ?? monitor['memory_warning_gb']}';
      _criticalCtrl.text = '${overrides['memory_critical_gb']?['value'] ?? monitor['memory_critical_gb']}';
      _intervalCtrl.text = '${overrides['request_interval']?['value'] ?? ''}';
      _templateCtrl.text =
          '${overrides['default_template']?['value'] ?? (summary['md2docx']?['default_template'] ?? '')}';
      setState(() {
        _summary = summary;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _saveOverrides() async {
    final api = ref.read(apiClientProvider);
    try {
      if (_warningCtrl.text.trim().isNotEmpty) {
        await api.setAppSetting('memory_warning_gb', double.parse(_warningCtrl.text));
      }
      if (_criticalCtrl.text.trim().isNotEmpty) {
        await api.setAppSetting('memory_critical_gb', double.parse(_criticalCtrl.text));
      }
      if (_intervalCtrl.text.trim().isNotEmpty) {
        await api.setAppSetting('request_interval', double.parse(_intervalCtrl.text));
      }
      if (_templateCtrl.text.trim().isNotEmpty) {
        await api.setAppSetting('default_template', _templateCtrl.text.trim());
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('覆盖设置已保存（app_settings）')),
      );
      await _refresh();
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('保存失败：[${e.code}] ${e.message}')),
      );
    }
  }

  Future<void> _resetToken() async {
    final api = ref.read(apiClientProvider);
    await api.resetToken();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Token 已重置（客户端下次请求自动重新读取）')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_error != null) {
      return Center(child: Text('加载失败：$_error', style: const TextStyle(color: Colors.red)));
    }
    final summary = _summary;
    if (summary == null) return const Center(child: CircularProgressIndicator());
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('设置', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('当前生效配置（config-summary）', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                Text(
                  '服务核心: ${summary['service']}\n'
                  '数据库: ${summary['database']}\n'
                  'AI: ${summary['ai']}\n'
                  '系统: ${summary['system']}',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('覆盖设置（保存到 app_settings）', style: theme.textTheme.titleMedium),
                const SizedBox(height: 12),
                TextField(
                  controller: _warningCtrl,
                  decoration: const InputDecoration(labelText: '内存黄色预警 (GB)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _criticalCtrl,
                  decoration: const InputDecoration(labelText: '内存红色告警 (GB)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _intervalCtrl,
                  decoration: const InputDecoration(labelText: '爬虫请求间隔 (秒)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _templateCtrl,
                  decoration: const InputDecoration(labelText: '默认 DOCX 模板'),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _saveOverrides,
                  icon: const Icon(Icons.save_outlined),
                  label: const Text('保存覆盖设置'),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.key_off_outlined),
            title: const Text('重置服务 Token'),
            subtitle: const Text('旧 token 立即失效，客户端自动重新读取'),
            trailing: OutlinedButton(onPressed: _resetToken, child: const Text('重置')),
          ),
        ),
      ],
    );
  }
}
