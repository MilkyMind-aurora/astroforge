import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 任务历史（Phase 1.4）：列表/筛选/详情/重试。
class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '任务历史',
      phase: 'Phase 1.4',
      description: 'PostgreSQL 持久化的任务记录：状态/类型筛选、日志回看（WS 补拉）、产物索引与一键重试。',
    );
  }
}
