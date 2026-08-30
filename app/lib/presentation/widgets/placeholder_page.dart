import 'package:flutter/material.dart';

/// 通用页面外壳：统一标题/功能说明/「建设中 · Phase X」徽标（方案 3.10）。
class PlaceholderPage extends StatelessWidget {
  const PlaceholderPage({
    required this.title,
    required this.description,
    required this.phase,
    super.key,
    this.child,
  });

  final String title;
  final String description;
  final String phase;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Row(
          children: [
            Text(title, style: theme.textTheme.headlineSmall),
            const SizedBox(width: 12),
            Chip(
              label: Text('建设中 · $phase', style: const TextStyle(fontSize: 12)),
              visualDensity: VisualDensity.compact,
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(description, style: theme.textTheme.bodyMedium),
        const SizedBox(height: 24),
        ?child,
      ],
    );
  }
}
