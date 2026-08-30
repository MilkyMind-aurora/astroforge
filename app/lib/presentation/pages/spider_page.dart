import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 采集中心（Phase 2）：四类爬取功能入口。
class SpiderPage extends StatelessWidget {
  const SpiderPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlaceholderPage(
      title: '采集中心',
      phase: 'Phase 2',
      description: 'Scrapling 自适应爬虫：单网页转 Markdown / 整站结构化爬取 / PDF 批量下载 / 数模表格抓取。',
    );
  }
}
