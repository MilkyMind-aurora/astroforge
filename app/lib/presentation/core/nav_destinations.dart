import 'package:flutter/material.dart';

/// 导航目标（供 NavigationRail 使用，与 TUI 侧边栏一一对应）。
const navDestinations = <(String, IconData)>[
  ('首页', Icons.rocket_launch_outlined),
  ('采集', Icons.travel_explore),
  ('解析', Icons.auto_stories_outlined),
  ('转换', Icons.swap_horiz),
  ('流水线', Icons.account_tree_outlined),
  ('监控', Icons.query_stats),
  ('历史', Icons.history),
  ('设置', Icons.settings_outlined),
];
