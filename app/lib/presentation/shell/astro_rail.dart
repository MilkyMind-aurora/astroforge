import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../core/mascot/starling_view.dart';
import '../core/nav_destinations.dart';

/// 壳层 72dp 图标轨（Kimi 式收窄轨，方案 §5.1 / 星空设计系统规格 §三.1）：
/// - 8 目的地星符图标（lucide 线性 20dp）；命中 48、视觉胶囊 36 R999；
/// - 选中 = aurora 实底胶囊 + onAurora 图标；胶囊滑移 = SPRING_SOFT（260/0.85）；
/// - 悬停 = container 底 + tooltip；健康点 6dp 右下（ok aurora/缺失 ink-400）；
/// - 轨底：星仔 28dp 圆头像（点击弹今日星语卡）+ 主题切换钮（明/暗/跟随）；
/// - <1200 宽折 48dp（§5.8 边界）。
class AstroRail extends ConsumerStatefulWidget {
  const AstroRail({
    required this.currentIndex,
    required this.onSelect,
    super.key,
  });

  final int currentIndex;
  final ValueChanged<int> onSelect;

  @override
  ConsumerState<AstroRail> createState() => _AstroRailState();
}

class _AstroRailState extends ConsumerState<AstroRail>
    with SingleTickerProviderStateMixin {
  late final AnimationController _capsule = AnimationController(vsync: this)
    ..value = widget.currentIndex.toDouble();

  static const double _itemExtent = 48.0;

  @override
  void didUpdateWidget(AstroRail oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.currentIndex != widget.currentIndex) {
      // 胶囊滑移：SPRING_SOFT（tokens.motion.spring_soft 260/0.85）——禁自造曲线
      final spring = SpringDescription(
        mass: 1,
        stiffness: AstroMotion.springSoft.stiffness,
        damping:
            AstroMotion.springSoft.damping * 2 * math.sqrt(AstroMotion.springSoft.stiffness),
      );
      _capsule.animateWith(
        SpringSimulation(
          spring,
          _capsule.value,
          widget.currentIndex.toDouble(),
          0,
        ),
      );
    }
  }

  @override
  void dispose() {
    _capsule.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final narrow = MediaQuery.sizeOf(context).width < 1200;
    final railWidth = narrow ? 48.0 : 72.0;
    final env = ref.watch(envCheckProvider).valueOrNull;

    return Container(
      width: railWidth,
      color: palette.bg,
      child: Column(
        children: [
          const SizedBox(height: 12),
          // 轨顶品牌星符（icons.yaml 语义星符——AstroIcons，禁散落字符）
          Text(
            AstroIcons.navHome,
            style: TextStyle(color: palette.aurora, fontSize: 22, height: 1),
          ),
          const Spacer(),
          // ---- 目的地 + 选中胶囊滑移指示 ----
          SizedBox(
            height: _itemExtent * navDestinations.length,
            width: railWidth,
            child: AnimatedBuilder(
              animation: _capsule,
              builder: (context, _) => Stack(
                children: [
                  Positioned(
                    top: _capsule.value * _itemExtent + (_itemExtent - 36) / 2,
                    left: (railWidth - 36) / 2,
                    child: Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: palette.aurora,
                        borderRadius: BorderRadius.circular(AstroRadius.pill),
                      ),
                    ),
                  ),
                  for (var i = 0; i < navDestinations.length; i++)
                    Positioned(
                      top: i * _itemExtent,
                      left: 0,
                      child: _RailItem(
                        destination: navDestinations[i],
                        index: i,
                        selected: i == widget.currentIndex,
                        narrow: narrow,
                        env: env,
                        onSelect: () => widget.onSelect(i),
                      ),
                    ),
                ],
              ),
            ),
          ),
          const Spacer(),
          // ---- 轨底：主题切换 + 星仔头像 ----
          const _ThemeToggle(),
          const SizedBox(height: 8),
          const _RailAvatar(),
          const SizedBox(height: 12),
        ],
      ),
    );
  }
}

class _RailItem extends StatefulWidget {
  const _RailItem({
    required this.destination,
    required this.index,
    required this.selected,
    required this.narrow,
    required this.env,
    required this.onSelect,
  });

  final AstroDestination destination;
  final int index;
  final bool selected;
  final bool narrow;
  final Map<String, dynamic>? env;
  final VoidCallback onSelect;

  @override
  State<_RailItem> createState() => _RailItemState();
}

class _RailItemState extends State<_RailItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final health = _healthLevel();
    return Tooltip(
      message: widget.destination.label,
      waitDuration: const Duration(milliseconds: 300),
      child: MouseRegion(
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTap: widget.onSelect,
          behavior: HitTestBehavior.opaque,
          child: Container(
            width: widget.narrow ? 48 : 72,
            height: 48.0,
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: Center(
              child: Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  // hover=container 底（规格 §三.1）；选中底由滑移胶囊承担
                  color: _hover && !widget.selected ? palette.container : null,
                  borderRadius: BorderRadius.circular(AstroRadius.pill),
                ),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Center(
                      child: Icon(
                        widget.destination.icon,
                        size: 20,
                        // 选中=onAurora；未选 ink-600（TWEEN_COLOR 150ms 换色）
                        color: widget.selected ? palette.onAurora : palette.ink600,
                      ),
                    ),
                    if (health != null)
                      Positioned(
                        right: 2,
                        bottom: 2,
                        child: _HealthDot(level: health, palette: palette),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// 健康点：env-check 项按名称映射（app_providers.railHealthEnvKeys）；
  /// 无对应环境项的目的地不显示健康点（禁伪造映射）。
  HealthLevel? _healthLevel() {
    final key = railHealthEnvKeys[widget.index];
    if (key == null) return null;
    final env = widget.env;
    if (env == null) return null;
    final items = (env['items'] as List<dynamic>? ?? const []);
    for (final item in items) {
      if ((item['name'] as String? ?? '').contains(key)) {
        return envItemHealth(item);
      }
    }
    return null;
  }
}

class _HealthDot extends StatelessWidget {
  const _HealthDot({required this.level, required this.palette});

  final HealthLevel level;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final color = switch (level) {
      HealthLevel.ok => palette.aurora,
      HealthLevel.missing => palette.ink400,
      HealthLevel.error => palette.nova,
      HealthLevel.unknown => palette.ink400,
    };
    return Container(
      width: 6,
      height: 6,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

/// 主题切换钮：明/暗/跟随三态循环（§5.1 轨底；触点圆形扩散主题转场为
/// 设置页 #2 动效，MF5 落位——此处仅切模式，走全局 250ms lerp）。
class _ThemeToggle extends ConsumerWidget {
  const _ThemeToggle();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final palette = AstroPaletteScope.of(context);
    final mode = ref.watch(astroThemeModeProvider);
    final controller = ref.read(astroThemeModeProvider.notifier);
    return IconButton(
      tooltip: switch (mode) {
        ThemeMode.system => '主题：跟随系统（点击切换为夜）',
        ThemeMode.dark => '主题：夜（点击切换为昼）',
        ThemeMode.light => '主题：昼（点击恢复跟随）',
      },
      onPressed: () {
        controller.setMode(switch (mode) {
          ThemeMode.system => AstroThemeMode.dark,
          ThemeMode.dark => AstroThemeMode.light,
          ThemeMode.light => AstroThemeMode.system,
        });
      },
      icon: Icon(
        switch (mode) {
          ThemeMode.system => LucideIcons.sunMoon,
          ThemeMode.dark => LucideIcons.moon,
          ThemeMode.light => LucideIcons.sun,
        },
        size: 18,
        color: palette.ink600,
      ),
    );
  }
}

/// 轨底星仔头像（28dp）：点击弹「今日星语」卡（日期种子当日固定）。
class _RailAvatar extends StatefulWidget {
  const _RailAvatar();

  @override
  State<_RailAvatar> createState() => _RailAvatarState();
}

class _RailAvatarState extends State<_RailAvatar> {
  Future<void> _openQuoteCard() async {
    final StarlingQuotes quotes;
    try {
      quotes = await StarlingQuotes.load();
    } catch (_) {
      return; // 台词库缺失静默（禁伪造文案）
    }
    if (!mounted) return;
    final palette = AstroPaletteScope.of(context);
    await showDialog<void>(
      context: context,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      builder: (dialogContext) => AlertDialog(
        backgroundColor: palette.cardRaised,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.lg),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const StarlingView(size: 72, primitive: StarlingPrimitive.starEyes),
            const SizedBox(height: AstroSpace.gap),
            Text(
              '今日星语',
              style: TextStyle(
                fontSize: AstroType.titleSm.size,
                fontWeight: FontWeight.w500,
                color: palette.ink900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              quotes.quoteOfDay(DateTime.now()),
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: AstroType.bodySm.size,
                height: AstroType.bodySm.height / AstroType.bodySm.size,
                color: palette.ink600,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text('收起', style: TextStyle(color: palette.ink600)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '星仔 · 今日星语',
      child: InkWell(
        onTap: _openQuoteCard,
        customBorder: const CircleBorder(),
        child: const StarlingView(size: 28),
      ),
    );
  }
}
