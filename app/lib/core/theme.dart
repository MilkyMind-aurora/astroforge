import 'package:flutter/material.dart';

/// 星尘主题（方案 3.10 / docs/design/design-system.md）。
/// 深空底 + 星尘紫主色 + 氢蓝辅助 + 熔金点缀；明暗两套同源。
class AstroForgeColors {
  AstroForgeColors._();

  static const deepSpace = Color(0xFF0B0E1A);
  static const stardustPurple = Color(0xFF8B7CF6);
  static const hydrogenBlue = Color(0xFF4FC3F7);
  static const moltenGold = Color(0xFFFFB74D);
  static const starWhite = Color(0xFFF5F3FF);
}

class AstroForgeTheme {
  AstroForgeTheme._();

  static ThemeData light() => _base(Brightness.light);

  static ThemeData dark() => _base(Brightness.dark);

  static ThemeData _base(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: AstroForgeColors.stardustPurple,
      brightness: brightness,
    );
    final isDark = brightness == Brightness.dark;
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: isDark ? AstroForgeColors.deepSpace : null,
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        isDense: true,
        filled: true,
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: isDark ? AstroForgeColors.deepSpace : null,
        selectedIconTheme: const IconThemeData(color: AstroForgeColors.hydrogenBlue),
        selectedLabelTextStyle: const TextStyle(
          color: AstroForgeColors.hydrogenBlue,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
