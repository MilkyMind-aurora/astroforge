import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../design/tokens.g.dart';
import '../router.dart';

/// 主题模式（§5.1 轨底主题切换钮：明/暗/跟随三态）。
enum AstroThemeMode { system, light, dark }

/// 主题模式控制器：shared_preferences 持久化（appearance.theme_mode 键；
/// 服务端 appearance.theme 为 TUI 主题包名，双端语义不同，设置页不对写——
/// Flutter 主题三选为客户端偏好；星野/星仔开关走 app_settings 双端同源）。
class AstroThemeController extends StateNotifier<ThemeMode> {
  AstroThemeController() : super(ThemeMode.system) {
    _restore();
  }

  static const _prefKey = 'appearance.theme_mode';

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefKey);
    if (saved == null || !mounted) return;
    state = switch (saved) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
  }

  void setMode(AstroThemeMode mode) {
    state = switch (mode) {
      AstroThemeMode.light => ThemeMode.light,
      AstroThemeMode.dark => ThemeMode.dark,
      AstroThemeMode.system => ThemeMode.system,
    };
    SharedPreferences.getInstance().then((p) {
      switch (state) {
        case ThemeMode.light:
          p.setString(_prefKey, 'light');
        case ThemeMode.dark:
          p.setString(_prefKey, 'dark');
        case ThemeMode.system:
          p.setString(_prefKey, 'system');
      }
    });
  }
}

final astroThemeModeProvider =
    StateNotifierProvider<AstroThemeController, ThemeMode>(
  (ref) => AstroThemeController(),
);

/// 星空调色板下发（§1.5：lerpPalette 全字段插值经本 scope 下发，
/// 组件零改动获得 250ms 同步过渡——组件一律 `AstroPaletteScope.of(context)` 取色）。
class AstroPaletteScope extends InheritedWidget {
  const AstroPaletteScope({
    required this.palette,
    required this.darkProgress,
    required super.child,
    super.key,
  });

  /// 当前插值色板（t∈(0,1) 时为过渡值）。
  final AstroPalette palette;

  /// 夜档进度 0..1（§1.5 darkProgress，TWEEN_THEME 250ms）。
  final double darkProgress;

  /// 组件取色唯一入口。
  static AstroPalette of(BuildContext context) {
    final scope = context
        .dependOnInheritedWidgetOfExactType<AstroPaletteScope>();
    assert(scope != null, 'AstroPaletteScope 未挂载：取色必须在根 scope 之下');
    return scope!.palette;
  }

  /// 夜档进度读取（星野昼夜 alpha 分档等场景）。
  static double darkProgressOf(BuildContext context) {
    final scope = context
        .dependOnInheritedWidgetOfExactType<AstroPaletteScope>();
    return scope?.darkProgress ?? 0;
  }

  @override
  bool updateShouldNotify(AstroPaletteScope oldWidget) =>
      oldWidget.palette != palette;
}

/// 触点圆形扩散主题切换（#2，B14#1/D24-G1）：
/// 旧主题层截屏冻结 → 切模式（下层即时换新主题）→ 冻结层按触点→最远角
/// 半径 clip 圆形擦除（280~350ms，裁切不缩放、字不变形）→ 新主题自孔洞 reveal。
/// reduced-motion：跳过扩散，瞬时切换（星仔规格 §五 降级表）。
class AstroThemeReveal {
  AstroThemeReveal._();

  static final GlobalKey _boundaryKey = GlobalKey();

  /// 主题切换入口（设置页三选/轨底钮共用；origin=触发点全局坐标）。
  static Future<void> change(
    BuildContext context,
    AstroThemeMode mode, {
    Offset? origin,
  }) async {
    final reduced = MediaQuery.disableAnimationsOf(context);
    final controller = ProviderScope.containerOf(context)
        .read(astroThemeModeProvider.notifier);
    if (reduced || origin == null) {
      controller.setMode(mode);
      return;
    }
    // overlay/boundary 在 await 前捕获（避免跨异步使用 context）
    final overlay = Overlay.of(context, rootOverlay: true);
    final boundary = _boundaryKey.currentContext?.findRenderObject()
        as RenderRepaintBoundary?;
    // ① 冻结旧主题帧（切换前截屏）
    ui.Image? frozen;
    if (boundary != null && boundary.attached) {
      try {
        final ratio = MediaQuery.devicePixelRatioOf(context);
        frozen = await boundary.toImage(pixelRatio: ratio.clamp(1.0, 3.0));
      } catch (_) {
        frozen = null; // 截屏失败退化为直接切换（无动画硬伤可接受）
      }
    }
    // ② 下层即时切换
    controller.setMode(mode);
    // ③ 冻结层圆形擦除 reveal
    late OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => _RevealOverlay(
        image: frozen!,
        origin: origin,
        onDone: () {
          if (entry.mounted) entry.remove();
          frozen?.dispose();
        },
      ),
    );
    if (frozen != null) {
      overlay.insert(entry);
    } else {
      frozen?.dispose();
    }
  }
}

class _RevealOverlay extends StatefulWidget {
  const _RevealOverlay({
    required this.image,
    required this.origin,
    required this.onDone,
  });

  final ui.Image image;
  final Offset origin;
  final VoidCallback onDone;

  @override
  State<_RevealOverlay> createState() => _RevealOverlayState();
}

class _RevealOverlayState extends State<_RevealOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 320), // dur-reveal 280~350ms
  )..forward();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final origin = widget.origin;
    // 触点 → 最远角半径（裁切不缩放）
    var maxDistance = 0.0;
    for (final corner in [
      Offset(0, 0),
      Offset(size.width, 0),
      Offset(0, size.height),
      Offset(size.width, size.height),
    ]) {
      maxDistance =
          maxDistance > (corner - origin).distance ? maxDistance : (corner - origin).distance;
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = Curves.easeOutCubic.transform(_controller.value);
        if (t >= 1) {
          WidgetsBinding.instance.addPostFrameCallback((_) => widget.onDone());
        }
        return CustomPaint(
          size: size,
          painter: _RevealPainter(
            image: widget.image,
            center: origin,
            radius: maxDistance * t,
          ),
        );
      },
    );
  }
}

/// 冻结旧帧 + dstOut 圆形擦除：孔内露出下层新主题，孔外保留旧帧。
class _RevealPainter extends CustomPainter {
  const _RevealPainter({
    required this.image,
    required this.center,
    required this.radius,
  });

  final ui.Image image;
  final Offset center;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.saveLayer(null, Paint());
    canvas.drawImageRect(
      image,
      Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble()),
      Offset.zero & size,
      Paint(),
    );
    canvas.drawCircle(center, radius, Paint()..blendMode = BlendMode.dstOut);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_RevealPainter oldDelegate) =>
      oldDelegate.radius != radius;
}

/// 根壳：把「主题模式 → 实际亮度 → darkProgress 250ms lerp」接到
/// MaterialApp（ThemeData.lerp）与 AstroPaletteScope（lerpPalette）两条线上。
/// 组件实现一律直用 token 名取色（AstroPalette.of），禁绕道 M3 role。
class AstroThemeScope extends ConsumerWidget {
  const AstroThemeScope({required this.child, super.key});

  final Widget child;

  static Brightness _resolve(ThemeMode mode, Brightness platform) => switch (mode) {
        ThemeMode.light => Brightness.light,
        ThemeMode.dark => Brightness.dark,
        ThemeMode.system => platform,
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(astroThemeModeProvider);
    // MaterialApp 自身先按目标档渲染，builder 里再对 MediaQuery 可见的实际亮度做动画。
    return MaterialApp.router(
      title: 'AstroForge · 衍星台',
      themeMode: mode,
      theme: AstroTheme.light(),
      darkTheme: AstroTheme.dark(),
      routerConfig: ref.watch(routerProvider),
      builder: (context, routerChild) {
        final platform = MediaQuery.platformBrightnessOf(context);
        final isDark = _resolve(mode, platform) == Brightness.dark;
        // reduced-motion（MediaQuery.disableAnimations / appearance.animation）
        // 主题切换瞬时完成（星仔规格 §五 降级表）。
        final instant = MediaQuery.disableAnimationsOf(context);
        return TweenAnimationBuilder<double>(
          tween: Tween(end: isDark ? 1.0 : 0.0),
          duration: instant
              ? Duration.zero
              : const Duration(milliseconds: AstroMotion.tweenThemeMs),
          curve: AstroMotion.tweenEasing,
          builder: (context, t, grandChild) {
            final palette = lerpPalette(AstroPalette.light, AstroPalette.dark, t);
            return Theme(
              data: ThemeData.lerp(AstroTheme.light(), AstroTheme.dark(), t),
              child: AstroPaletteScope(
                palette: palette,
                darkProgress: t,
                child: grandChild!,
              ),
            );
          },
          // RepaintBoundary：#2 触点圆形扩散的旧主题帧截屏源
          child: RepaintBoundary(
            key: AstroThemeReveal._boundaryKey,
            child: routerChild,
          ),
        );
      },
    );
  }
}
