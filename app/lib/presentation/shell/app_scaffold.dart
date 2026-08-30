import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../ai/ai_drawer.dart';
import '../core/nav_destinations.dart';

/// NavigationRail 外壳（方案 3.10）：8 目的地 + AI 抽屉入口。
/// 连接状态徽标随 Phase 9.2.3 接入 WS 状态流。
class AppScaffold extends StatelessWidget {
  const AppScaffold({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  void _onDestinationSelected(int index) {
    navigationShell.goBranch(index, initialLocation: index == navigationShell.currentIndex);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AstroForge · 衍星台'),
        actions: [
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Chip(
              avatar: CircleAvatar(backgroundColor: Colors.grey, radius: 5),
              label: Text('本机服务', style: TextStyle(fontSize: 12)),
              visualDensity: VisualDensity.compact,
            ),
          ),
          IconButton(
            tooltip: '星伴 AI（Ctrl+Shift+A）',
            icon: const Icon(Icons.auto_awesome),
            onPressed: () => Scaffold.of(context).openEndDrawer(),
          ),
          const SizedBox(width: 8),
        ],
      ),
      endDrawer: const AiDrawer(),
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: navigationShell.currentIndex,
            onDestinationSelected: _onDestinationSelected,
            labelType: NavigationRailLabelType.all,
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('✦', style: TextStyle(fontSize: 24)),
            ),
            destinations: [
              for (final (label, icon) in navDestinations)
                NavigationRailDestination(icon: Icon(icon), label: Text(label)),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: navigationShell),
        ],
      ),
    );
  }
}
