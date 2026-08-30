import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 转换中心（Phase 4）：anydoc 入转换 + md2docx 出转换。
class ConverterPage extends StatelessWidget {
  const ConverterPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '转换中心',
      phase: 'Phase 4',
      description: 'anydoc 办公文档批量转 Markdown（Rust）；md2docx 模板化转 Word（5 套场景模板）。',
    );
  }
}
