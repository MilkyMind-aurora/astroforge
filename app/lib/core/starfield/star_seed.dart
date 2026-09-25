import 'dart:convert';

import 'package:flutter/services.dart';

/// 星野种子（config/design/starfield/seed.json 的镜像资产，
/// scripts/gen_design.py 生成——三端同源，禁每帧随机）。
class StarSeed {
  const StarSeed({
    required this.seed,
    required this.stars,
    required this.densityMin,
    required this.densityMax,
  });

  final int seed;
  final List<StarDot> stars;
  final int densityMin;
  final int densityMax;

  static Future<StarSeed> loadAsset([String assetPath =
      'assets/design/starfield/seed.json']) async {
    final raw = await rootBundle.loadString(assetPath);
    return fromJsonString(raw);
  }

  static StarSeed fromJsonString(String raw) {
    final data = jsonDecode(raw) as Map<String, dynamic>;
    final stars = (data['stars'] as List<dynamic>)
        .map((s) => StarDot(
              x: (s['x'] as num).toDouble(),
              y: (s['y'] as num).toDouble(),
              tier: (s['tier'] as num).toInt(),
              phase: (s['phase'] as num).toDouble(),
            ))
        .toList(growable: false);
    final density = (data['density'] as List<dynamic>).cast<int>();
    return StarSeed(
      seed: (data['seed'] as num).toInt(),
      stars: stars,
      densityMin: density.first,
      densityMax: density.last,
    );
  }
}

class StarDot {
  const StarDot({
    required this.x,
    required this.y,
    required this.tier,
    required this.phase,
  });

  /// 归一化坐标 0..1
  final double x;
  final double y;

  /// 星等三档 0/1/2 → alpha 0.04/0.08/0.12、直径 1/1.5/2dp
  final int tier;
  final double phase;
}
