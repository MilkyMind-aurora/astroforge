import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

/// 导航目的地（壳层 72dp 图标轨；图标=lucide 线性 20dp，方案 §5.1/§1.6）。
/// IA 裁决 8→5（UX 评审总裁决/V1.1-4，MF5 落地）：首页/任务/流水线/历史/设置。
/// 采集/解析/转换三合一为「任务」页；监控降级为右上仪表胶囊+弹层（壳层）。
/// TUI 保留 8 页（数字键肌肉记忆）——双端纪律放宽为
/// 「任务数据互通+术语一致+快捷键语义对齐」（页面映射不强制）。
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
  AstroDestination(label: '任务', icon: LucideIcons.hammer, path: '/tasks'),
  AstroDestination(label: '流水线', icon: LucideIcons.workflow, path: '/pipeline'),
  AstroDestination(label: '历史', icon: LucideIcons.history, path: '/history'),
  AstroDestination(label: '设置', icon: LucideIcons.settings, path: '/settings'),
];
