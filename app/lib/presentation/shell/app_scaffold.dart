import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../core/starfield/starfield_view.dart';
import '../../data/api_client/dio_client.dart';
import '../ai/ai_drawer.dart';
import '../monitor/gauge_capsule.dart';
import '../widgets/aurora_banner.dart';
import '../widgets/command_palette.dart';
import '../widgets/drag_task_layer.dart';
import '../widgets/log_panel.dart';
import 'astro_rail.dart';
import 'astro_shortcuts.dart';
import 'disconnect_banner.dart';

/// 星舰外壳（方案 §5.1 / MF5）：底层星野画布 + 左侧 72dp 图标轨 +
/// 右上仪表胶囊（IA 裁决：监控降级，兼常驻服务连接态）+ 断连挤压横幅 +
/// 全局拖拽建任务层（UX P0-4）+ 任务完成极光横幅（§1.8 #18 白名单位①）。
/// Scaffold 底透明——星点只落在留白区，内容卡一律 card 底不透明（对比度纪律）。
class AppScaffold extends ConsumerStatefulWidget {
  const AppScaffold({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppScaffold> createState() => _AppScaffoldState();
}

class _AppScaffoldState extends ConsumerState<AppScaffold> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  TaskCompletion? _aurora; // 当前展示的完成横幅（3s 自动退场）

  void _onDestinationSelected(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
  }

  @override
  void initState() {
    super.initState();
    // 外观开关尽力同步服务端 app_settings（appearance.*）
    Future<void>.microtask(() =>
        ref.read(appearanceProvider.notifier).attachApi(ref.read(apiClientProvider)));
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final starfieldOn = ref.watch(appearanceProvider).starfield;
    // #18 任务完成极光横幅：WS status 事件确认完成后全局触达（历史页/流水线发布）
    ref.listen(taskCompletionsProvider, (_, _) {
      final latest = ref.read(taskCompletionsProvider.notifier).latest;
      if (latest != null && latest != _aurora) {
        setState(() => _aurora = latest);
      }
    });
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
          OpenPaletteIntent: CallbackAction<OpenPaletteIntent>(
            onInvoke: (_) async {
              await CommandPalette.show(context);
              return null;
            },
          ),
          OpenLogPanelIntent: CallbackAction<OpenLogPanelIntent>(
            onInvoke: (_) async {
              await LogPanel.show(context);
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
          // 全局拖拽落点（挂壳层，禁只绑首页——UX P0-4）
          body: DragTaskLayer(
            child: Stack(
              children: [
                // S0 页面底（MF6 双主题金测发现：Scaffold 透明 + 星野画布透明，
                // 此前无任何层涂 bg——夜档被 #05070F≈纯黑掩盖，昼档直接露出
                // 黑底白卡。星点必须落在 bg 之上、内容卡之下，对比度纪律不变）
                Positioned.fill(
                  child: ColoredBox(color: palette.bg),
                ),
                // 星野背景（seed.json/uSeed 驱动；失焦暂停；弹层打开流星让位；
                // 设置页 appearance.starfield 开关即时生效）
                if (starfieldOn) const Positioned.fill(child: StarfieldView()),
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
                // 右上仪表胶囊（常驻：连接态 + CPU/内存实时值 → 点击展开星象台）
                const Positioned(
                  top: AstroSpace.window,
                  right: AstroSpace.window,
                  child: GaugeCapsule(),
                ),
                // #18 任务完成极光横幅（渐变白名单位①：galaxy 三停驻+高光扫过；
                // 顶部居中，3s 自动退场——同屏常驻渐变仍只有 AI 抽屉头饰线）
                if (_aurora != null)
                  Positioned(
                    top: AstroSpace.window + 44,
                    left: 0,
                    right: 0,
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 420),
                        child: AuroraBanner(
                          key: ValueKey(_aurora!.taskUuid),
                          message: '任务完成 · ${_aurora!.title}',
                          onDismissed: () {
                            if (mounted) setState(() => _aurora = null);
                          },
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
