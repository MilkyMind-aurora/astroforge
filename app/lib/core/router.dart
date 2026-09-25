import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../presentation/pages/history_page.dart';
import '../presentation/pages/home_page.dart';
import '../presentation/pages/pipeline_page.dart';
import '../presentation/pages/settings_page.dart';
import '../presentation/pages/task_page.dart';
import '../presentation/shell/app_scaffold.dart';

/// 5 大页面路由（IA 裁决 8→5，UX 评审总裁决 / 方案 V1.1-4，MF5 落地）：
/// 首页/任务/流水线/历史/设置。旧 8 页路径重定向（任务页三合一；
/// 监控降级为右上仪表胶囊，无独立路由）。
final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) {
      const legacyMap = <String, String>{
        '/spider': '/tasks',
        '/parser': '/tasks',
        '/converter': '/tasks',
        '/monitor': '/home',
      };
      return legacyMap[state.uri.path];
    },
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppScaffold(navigationShell: navigationShell),
        branches: [
          _branch('/home', const HomePage()),
          _branch('/tasks', const TaskPage()),
          _branch('/pipeline', const PipelinePage()),
          _branch('/history', const HistoryPage()),
          _branch('/settings', const SettingsPage()),
        ],
      ),
    ],
  );
});

StatefulShellBranch _branch(String path, Widget page) {
  return StatefulShellBranch(
    routes: [
      GoRoute(path: path, builder: (context, state) => page),
    ],
  );
}
