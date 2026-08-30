import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 流水线（Phase 5）：NovaFlow 编排。
class PipelinePage extends StatelessWidget {
  const PipelinePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '流水线',
      phase: 'Phase 5',
      description: 'NovaFlow 流水线引擎：内置模板（学术论文/文档采集/办公批量/数模数据）一键全链路，支持断点续跑与自定义 YAML。',
    );
  }
}
