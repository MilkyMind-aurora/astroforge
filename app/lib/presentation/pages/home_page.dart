import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/api_client/dio_client.dart';

/// 首页：环境状态卡（真实调用 /system/health + /system/env-check）。
class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  Map<String, dynamic>? _health;
  Map<String, dynamic>? _env;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final health = await api.health();
      final env = await api.envCheck();
      if (!mounted) return;
      setState(() {
        _health = health;
        _env = env;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } catch (e) {
      // DioException（401/网络层）等非业务异常同样转连接引导态
      if (!mounted) return;
      setState(() => _error = '服务不可达或 token 缺失（$e）');
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_error != null) {
      return _ConnectGuide(error: _error!, onRetry: _refresh);
    }
    final health = _health;
    if (health == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final env = _env ?? {};
    final items = (env['items'] as List<dynamic>? ?? const []);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('首页', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text('Forging Order from Stellar Chaos.',
            style: theme.textTheme.bodySmall),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                const Icon(Icons.dns_outlined),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Sidereal Core v${health['version']} · 运行 ${health['uptime_s']}s · '
                    'DB ${health['db'] == true ? '✅' : '❌'} · '
                    'AI 引擎 ${health['ai_engine'] == true ? '✅' : '💤'}',
                  ),
                ),
                IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh)),
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
                Text('环境体检 ${env['ok_count'] ?? '-'}/${env['total'] ?? '-'}',
                    style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                for (final item in items)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        Text(item['ok'] == true ? '✅' : '❌'),
                        const SizedBox(width: 8),
                        Expanded(child: Text('${item['name']}  ${item['detail']}',
                            style: theme.textTheme.bodySmall)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// 连接引导（失败态内嵌，方案 3.10 连接引导页）。
class _ConnectGuide extends StatelessWidget {
  const _ConnectGuide({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('🔭 连不上 Sidereal Core', style: TextStyle(fontSize: 18)),
          const SizedBox(height: 8),
          Text('服务核心未启动（$error）',
              style: const TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          const Text('Windows: scripts\\start_service.bat\nmacOS:   bash scripts/start_service.sh',
              textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('重试连接'),
          ),
        ],
      ),
    );
  }
}
