import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../monitor/monitor_sheet.dart';

/// 命令面板（Ctrl+K；TUI `/` 同名映射，方案 §5.1）：
/// 命令全集 = 5 页导航（IA 8→5）/ 星象台弹层 / 星伴抽屉 / 刷新 / 主题三切 /
/// 重连。子串命中即可（不做拼音【继承 TUI 纪律】）；本地过滤为瞬时档
/// （禁全屏 loading，输入即过滤——无网络往返，防抖无意义如实省略）。
class CommandPalette extends ConsumerStatefulWidget {
  const CommandPalette({required this.onClose, super.key});

  final VoidCallback onClose;

  static Future<void> show(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return showDialog<void>(
      context: context,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      barrierLabel: '命令面板',
      builder: (dialogContext) => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: CommandPalette(onClose: () => Navigator.of(dialogContext).pop()),
        ),
      ),
    );
  }

  @override
  ConsumerState<CommandPalette> createState() => _CommandPaletteState();
}

class _CommandPaletteState extends ConsumerState<CommandPalette> {
  final _queryCtrl = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _queryCtrl.dispose();
    super.dispose();
  }

  List<(String, String, IconData, void Function(BuildContext))> get _commands => [
        ('nav.home', '去首页', LucideIcons.house, (c) => c.go('/home')),
        ('nav.tasks', '去任务页', LucideIcons.hammer, (c) => c.go('/tasks')),
        ('nav.pipeline', '去流水线', LucideIcons.workflow, (c) => c.go('/pipeline')),
        ('nav.history', '去任务历史', LucideIcons.history, (c) => c.go('/history')),
        ('nav.settings', '去设置', LucideIcons.settings, (c) => c.go('/settings')),
        (
          'monitor',
          '打开星象台（监控弹层）',
          LucideIcons.activity,
          (c) => MonitorSheet.show(c),
        ),
        (
          'refresh',
          '刷新当前页数据（F5）',
          LucideIcons.refreshCw,
          (c) => ProviderScope.containerOf(c).read(refreshEventsProvider.notifier).refreshRequested(),
        ),
        (
          'theme.dark',
          '切换主题为夜',
          LucideIcons.moon,
          (c) => AstroThemeReveal.change(c, AstroThemeMode.dark),
        ),
        (
          'theme.light',
          '切换主题为昼',
          LucideIcons.sun,
          (c) => AstroThemeReveal.change(c, AstroThemeMode.light),
        ),
        (
          'theme.system',
          '切换主题为跟随系统',
          LucideIcons.sunMoon,
          (c) => AstroThemeReveal.change(c, AstroThemeMode.system),
        ),
        (
          'reconnect',
          '重连服务（WS）',
          LucideIcons.antenna,
          (c) => ProviderScope.containerOf(c).read(connectionProvider.notifier).nudgeReconnect(),
        ),
      ];

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final hits = _commands
        .where((cmd) => cmd.$2.toLowerCase().contains(_query.toLowerCase()))
        .toList();
    return Material(
      color: palette.cardRaised,
      borderRadius: BorderRadius.circular(AstroRadius.lg),
      elevation: 0,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AstroRadius.lg),
          border: Border.all(color: palette.stroke),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Row(
                children: [
                  Icon(LucideIcons.search, size: 16, color: palette.ink400),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextField(
                      controller: _queryCtrl,
                      autofocus: true,
                      style: TextStyle(
                          fontSize: AstroType.body.size, color: palette.ink900),
                      cursorColor: palette.aurora,
                      decoration: InputDecoration.collapsed(
                        hintText: '输入命令…（子串命中）',
                        hintStyle: TextStyle(
                            fontSize: AstroType.bodySm.size,
                            color: palette.ink400),
                      ),
                      onChanged: (v) => setState(() => _query = v),
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 320),
              child: hits.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text('无命中命令',
                          style: TextStyle(
                              fontSize: AstroType.bodySm.size,
                              color: palette.ink400)),
                    )
                  : ListView(
                      shrinkWrap: true,
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      children: [
                        for (final (key, label, icon, action) in hits)
                          ListTile(
                            key: ValueKey(key),
                            dense: true,
                            leading: Icon(icon,
                                size: 18, color: palette.ink600),
                            title: Text(label,
                                style: TextStyle(
                                    fontSize: AstroType.bodySm.size,
                                    color: palette.ink900)),
                            onTap: () {
                              widget.onClose();
                              action(context);
                            },
                          ),
                      ],
                    ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
              child: Row(
                children: [
                  Text('Ctrl+K 打开 · Esc 关闭',
                      style: TextStyle(
                          fontSize: AstroType.label.size,
                          color: palette.ink400)),
                  const Spacer(),
                  Text('${hits.length} 项',
                      style: TextStyle(
                          fontSize: AstroType.label.size,
                          color: palette.ink400)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
