import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 设置（Phase 1.3）。
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '设置',
      phase: 'Phase 1.3',
      description: '路径配置、内存限制、AI 配置、监控阈值、主题切换、服务端口与 token 重置（经服务 API）。',
    );
  }
}
