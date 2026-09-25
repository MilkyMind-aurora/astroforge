// 星空设计契约测试：lerpPalette 全字段过渡 / AstroTheme 手写 ColorScheme（禁 fromSeed）。
import 'dart:math';

import 'package:astroforge/core/design/design.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('lerpPalette（§1.5 TWEEN_THEME 250ms 基建）', () {
    test('t=0/t=1 返回端点实例', () {
      expect(identical(lerpPalette(AstroPalette.light, AstroPalette.dark, 0.0),
          AstroPalette.light), isTrue);
      expect(identical(lerpPalette(AstroPalette.light, AstroPalette.dark, 1.0),
          AstroPalette.dark), isTrue);
    });

    test('中点插值落在昼/夜端点之间（全字段抽查）', () {
      final mid = lerpPalette(AstroPalette.light, AstroPalette.dark, 0.5);
      for (final (a, b, m) in [
        (AstroPalette.light.bg, AstroPalette.dark.bg, mid.bg),
        (AstroPalette.light.aurora, AstroPalette.dark.aurora, mid.aurora),
        (AstroPalette.light.ink900, AstroPalette.dark.ink900, mid.ink900),
        (AstroPalette.light.chipsSelectedBg, AstroPalette.dark.chipsSelectedBg,
            mid.chipsSelectedBg),
        (AstroPalette.light.galaxyStop1, AstroPalette.dark.galaxyStop1,
            mid.galaxyStop1),
      ]) {
        expect(m.r, inInclusiveRange(min(a.r, b.r), max(a.r, b.r)));
        expect(m.g, inInclusiveRange(min(a.g, b.g), max(a.g, b.g)));
        expect(m.b, inInclusiveRange(min(a.b, b.b), max(a.b, b.b)));
      }
    });
  });

  group('AstroTheme（星空设计系统规格 §六：手写 ColorScheme，禁 fromSeed）', () {
    test('夜档 primary=aurora 夜值、surface=card、背景=bg', () {
      final theme = AstroTheme.dark();
      expect(theme.colorScheme.primary, AstroPalette.dark.aurora);
      expect(theme.colorScheme.surface, AstroPalette.dark.card);
      expect(theme.scaffoldBackgroundColor, AstroPalette.dark.bg);
      // aurora 实底文字一律深字（硬裁定：禁白字）
      expect(theme.colorScheme.onPrimary, AstroPalette.dark.onAurora);
    });

    test('昼档 primary=aurora 昼值（Material 默认种子紫不复活）', () {
      final theme = AstroTheme.light();
      expect(theme.colorScheme.primary, AstroPalette.light.aurora);
      expect(theme.scaffoldBackgroundColor, AstroPalette.light.bg);
      // Material 默认紫 #6750A4 断言排除
      expect(theme.colorScheme.primary, isNot(const Color(0xFF6750A4)));
    });

    test('圆角四档收敛 999/20/16/12（规格 §〇-8）', () {
      expect(AstroRadius.pill, 999.0);
      expect(AstroRadius.lg, 20.0);
      expect(AstroRadius.md, 16.0);
      expect(AstroRadius.sm, 12.0);
    });
  });
}
