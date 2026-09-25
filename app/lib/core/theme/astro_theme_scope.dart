import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../design/tokens.g.dart';
import '../router.dart';

/// 主题模式（§5.1 轨底主题切换钮：明/暗/跟随三态）。
enum AstroThemeMode { system, light, dark }

/// 主题模式控制器：shared_preferences 持久化（appearance.theme_mode 键；
/// 服务端 appearance.theme 为 TUI 主题包名，双端语义不同，MF5 设置页再对齐）。
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
          child: routerChild,
        );
      },
    );
  }
}
