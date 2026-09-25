import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

/// 导航目的地（壳层 72dp 图标轨；图标=lucide 线性 20dp，方案 §5.1/§1.6）。
/// 与 TUI 侧边栏一一对应（8 目的地）；V1.1-4 IA 裁决 8→5 的三合一「任务」页
/// 属 MF5 表单卡族合并时落地，合并时仅需改本表（见 milestone notes）。
class AstroDestination {
  const AstroDestination({
    required this.label,
    required this.icon,
    required this.path,
  });

  final String label;
  final IconData icon;
  final String path;
}

const navDestinations = <AstroDestination>[
  AstroDestination(label: '首页', icon: LucideIcons.house, path: '/home'),
  AstroDestination(label: '采集', icon: LucideIcons.globe, path: '/spider'),
  AstroDestination(label: '解析', icon: LucideIcons.fileScan, path: '/parser'),
  AstroDestination(label: '转换', icon: LucideIcons.arrowRightLeft, path: '/converter'),
  AstroDestination(label: '流水线', icon: LucideIcons.workflow, path: '/pipeline'),
  AstroDestination(label: '监控', icon: LucideIcons.activity, path: '/monitor'),
  AstroDestination(label: '历史', icon: LucideIcons.history, path: '/history'),
  AstroDestination(label: '设置', icon: LucideIcons.settings, path: '/settings'),
];
