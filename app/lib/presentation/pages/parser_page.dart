import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 解析中心（Phase 3）：MinerU + WPD。
class ParserPage extends StatelessWidget {
  const ParserPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '解析中心',
      phase: 'Phase 3',
      description: 'MinerU 文档结构化解析（PDF/图片 → Markdown）+ WebPlotDigitizer 图表数值提取（CSV）。',
    );
  }
}
