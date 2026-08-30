import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../presentation/pages/converter_page.dart';
import '../presentation/pages/home_page.dart';
import '../presentation/pages/history_page.dart';
import '../presentation/pages/monitor_page.dart';
import '../presentation/pages/parser_page.dart';
import '../presentation/pages/pipeline_page.dart';
import '../presentation/pages/settings_page.dart';
import '../presentation/pages/spider_page.dart';
import '../presentation/shell/app_scaffold.dart';

/// 8 大页面路由（方案 3.10，与 TUI 一一对应）。
final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/home',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppScaffold(navigationShell: navigationShell),
        branches: [
          _branch('/home', const HomePage()),
          _branch('/spider', const SpiderPage()),
          _branch('/parser', const ParserPage()),
          _branch('/converter', const ConverterPage()),
          _branch('/pipeline', const PipelinePage()),
          _branch('/monitor', const MonitorPage()),
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
