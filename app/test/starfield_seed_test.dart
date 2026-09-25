// 星野种子与 Canvas 降级 painter 测试（§1.5：seed.json 预生成、三端同源、禁每帧随机）。
import 'package:astroforge/core/design/design.dart';
import 'package:astroforge/core/starfield/star_seed.dart';
import 'package:astroforge/core/starfield/starfield_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('StarSeed（config/design/starfield/seed.json 镜像资产）', () {
    test('资产可加载：60~90 颗、tier 三档、坐标归一化', () async {
      final seed = await StarSeed.loadAsset();
      expect(seed.stars.length, inInclusiveRange(seed.densityMin, seed.densityMax));
      expect(AstroStarfield.densityMin, lessThanOrEqualTo(seed.stars.length));
      expect(seed.stars.length, lessThanOrEqualTo(AstroStarfield.densityMax));
      for (final star in seed.stars) {
        expect(star.x, inInclusiveRange(0.0, 1.0));
        expect(star.y, inInclusiveRange(0.0, 1.0));
        expect(star.tier, inInclusiveRange(0, 2));
      }
    });

    test('同字节解析幂等（同种子必同星象）', () async {
      final raw = await StarSeed.loadAsset();
      final again = await StarSeed.loadAsset();
      expect(again.stars.length, raw.stars.length);
      expect(again.seed, raw.seed);
      expect(again.stars.first.x, raw.stars.first.x);
    });
  });

  group('StarfieldCanvasPainter（golden 降级路径）', () {
    testWidgets('冻结 uTime=0 渲染无异常（golden test 冻结纪律）', (tester) async {
      StarSeed? seed;
      await tester.runAsync(() async {
        seed = await StarSeed.loadAsset();
      });
      expect(seed, isNotNull);
      await tester.pumpWidget(CustomPaint(
        painter: StarfieldCanvasPainter(
          seed: seed!,
          palette: AstroPalette.dark,
          time: 0, // 冻结
          alphaMax: AstroStarfield.alphaSteps.last,
        ),
        size: const Size(400, 300),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });
}
