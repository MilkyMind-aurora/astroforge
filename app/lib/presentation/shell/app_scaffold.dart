import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../core/starfield/starfield_view.dart';
import '../ai/ai_drawer.dart';
import 'astro_rail.dart';
import 'astro_shortcuts.dart';
import 'disconnect_banner.dart';

/// 星舰外壳（方案 §5.1）：底层星野画布 + 左侧 72dp 图标轨 + 断连挤压横幅。
/// Scaffold 底透明——星点只落在留白区，内容卡一律 card 底不透明（对比度纪律）。
class AppScaffold extends ConsumerStatefulWidget {
  const AppScaffold({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppScaffold> createState() => _AppScaffoldState();
}

class _AppScaffoldState extends ConsumerState<AppScaffold> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  void _onDestinationSelected(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Shortcuts(
      shortcuts: astroShortcuts(),
      child: Actions(
        actions: {
          OpenAiDrawerIntent: CallbackAction<OpenAiDrawerIntent>(
            onInvoke: (_) async {
              // Ctrl+Shift+A 星伴抽屉（修复旧「仅 tooltip 无绑定」）
              _scaffoldKey.currentState?.openEndDrawer();
              return null;
            },
          ),
          NavBranchIntent: CallbackAction<NavBranchIntent>(
            onInvoke: (intent) {
              _onDestinationSelected(intent.index);
              return null;
            },
          ),
          RefreshIntent: CallbackAction<RefreshIntent>(
            onInvoke: (_) {
              ref.read(refreshEventsProvider.notifier).refreshRequested();
              return null;
            },
          ),
          EscapeLayerIntent: CallbackAction<EscapeLayerIntent>(
            onInvoke: (_) {
              FocusManager.instance.primaryFocus?.unfocus();
              return null;
            },
          ),
          // SendIntent / FocusComposerIntent 由聚焦中的输入条（composer）
          // 自带 Actions 就近接管——shell 不兜底（§5.1 Ctrl+Enter/Ctrl+I 语义）。
        },
        child: Scaffold(
          key: _scaffoldKey,
          backgroundColor: palette.bg.withValues(alpha: 0),
          endDrawer: const AiDrawer(),
          onEndDrawerChanged: (open) {
            if (!open) FocusManager.instance.primaryFocus?.unfocus();
          },
          body: Stack(
            children: [
              // 星野背景（seed.json/uSeed 驱动；失焦暂停；弹层打开流星让位）
              const Positioned.fill(child: StarfieldView()),
              Column(
                children: [
                  const DisconnectBanner(),
                  Expanded(
                    child: Row(
                      children: [
                        AstroRail(
                          currentIndex: widget.navigationShell.currentIndex,
                          onSelect: _onDestinationSelected,
                        ),
                        Expanded(child: widget.navigationShell),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
