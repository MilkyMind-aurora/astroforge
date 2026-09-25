import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../design/design.dart';
import 'starling_engine.dart';

/// 星仔 painter（星仔规格 V2-2/V2-4）：CustomPainter 消费 sampleStarling 单帧——
/// 径向轮廓星云本体 + 椭圆星环（含 6~9 颗公转星点）+ 遮罩挖洞眼睛。
/// 颜色一律来自 AstroPalette（nebula/hydrogen 星云渐变、aurora 环、molten 火星——
/// V1 色彩纪律：thinking/speaking 只用 nebula，happy/celebrate 只用 molten，
/// error 烟/负面一律 ink-600，错误语义留给任务卡）。
class StarlingPainter extends CustomPainter {
  StarlingPainter({
    required this.pose,
    required this.palette,
    required this.backgroundColor,
    this.ringStarCount = 7,
  });

  final StarlingPose pose;
  final AstroPalette palette;
  final Color backgroundColor;
  final int ringStarCount;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide * 0.30; // 本体半径基准（120dp 画布 → 36dp 半径）
    final r = radius * pose.bodyScaleX;
    final ry = radius * pose.bodyScaleY;

    // ---- 星环（背面半环 → 本体 → 正面半环，形成「穿过」层次）----
    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(pose.ringTiltDeg * math.pi / 180);
    final ringLong = radius * 1.8; // 长轴 1.8×本体直径
    final ringShort = radius * 0.5; // 短轴 0.5×
    _drawRingArc(canvas, ringLong, ringShort, back: true);
    _drawRingStars(canvas, ringLong, ringShort, back: true);
    _drawRingArc(canvas, ringLong, ringShort, back: false);
    _drawRingStars(canvas, ringLong, ringShort, back: false);
    canvas.restore();

    // ---- 本体：近正圆星云（nebula→hydrogen 135° 柔和渐变 + 暗斑纹理）----
    final bodyPath = Path()..addOval(Rect.fromCenter(
        center: center, width: r * 2, height: ry * 2));
    final gradient = Paint()
      ..shader = SweepGradient(
        startAngle: 0,
        endAngle: 2 * math.pi,
        colors: [palette.nebula, palette.hydrogen, palette.nebula],
        transform: const GradientRotation(-3 * math.pi / 4), // 135° 观感
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawPath(bodyPath, gradient);

    // 暗斑纹理：3 枚低透明暗点表现「星球表面」（位置由固定比例推导，非随机）
    final spotPaint = Paint()
      ..color = palette.bg.withValues(alpha: 0.10)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(
        center + Offset(radius * 0.38, -radius * 0.30), radius * 0.22, spotPaint);
    canvas.drawCircle(
        center + Offset(-radius * 0.30, radius * 0.26), radius * 0.14, spotPaint);
    canvas.drawCircle(
        center + Offset(-radius * 0.05, -radius * 0.52), radius * 0.10, spotPaint);

    // ---- 遮罩挖洞眼睛（bloub 同技术：Path.difference 挖出真孔露底色）----
    final holes = Path();
    _addEyeHole(holes, center, radius, left: true);
    _addEyeHole(holes, center, radius, left: false);
    if (pose.mouthOpen > 0.05) {
      // speaking 小弧线孔洞（idle 无嘴——星球更纯粹）
      final mouthRect = Rect.fromCenter(
        center: center + Offset(0, radius * 0.42),
        width: radius * 0.34,
        height: radius * 0.10 + radius * 0.18 * pose.mouthOpen,
      );
      holes.addOval(mouthRect);
    }
    canvas.drawPath(
      Path.combine(PathOperation.difference, bodyPath, holes),
      Paint()..color = backgroundColor,
    );

    // ---- 眼形变化（挖洞之上的强调层）----
    if (pose.crossedEyes) {
      _drawCrossedEyes(canvas, center, radius);
    }

    // ---- blush 双颊（aurora@20% 圆晕）----
    if (pose.blushAlpha > 0.01) {
      final blushPaint = Paint()
        ..color = palette.aurora.withValues(alpha: 0.20 * pose.blushAlpha);
      canvas.drawCircle(
          center + Offset(radius * 0.55, radius * 0.25), radius * 0.16, blushPaint);
      canvas.drawCircle(
          center + Offset(-radius * 0.55, radius * 0.25), radius * 0.16, blushPaint);
    }

    // ---- 氛围微粒星光（本体外围 3~5 颗缓漂，alpha ≤0.12 同星野纪律）----
    final dustPaint = Paint()
      ..color = palette.ink600.withValues(alpha: 0.12);
    for (var i = 0; i < 4; i++) {
      final angle = 2 * math.pi * i / 4 + pose.ringSpinRad * 0.2;
      final orbit = radius * (1.45 + 0.08 * math.sin(angle * 3));
      canvas.drawCircle(
        center + Offset(math.cos(angle) * orbit, math.sin(angle) * orbit * 0.7),
        1.0,
        dustPaint,
      );
    }
  }

  void _addEyeHole(Path holes, Offset center, double radius,
      {required bool left}) {
    final open = (left ? pose.eyeOpennessL : pose.eyeOpennessR).clamp(0.0, 1.0);
    final sign = left ? -1.0 : 1.0;
    final eyeCenter = center +
        Offset(sign * radius * 0.34 + pose.gazeOffset.dx,
            -radius * 0.10 + pose.gazeOffset.dy);
    if (pose.starEyes || pose.heartEyes) {
      // ✦/♥ 形眼：四角星形孔洞（heart 首版以星形近似，梦幻时刻专用）
      final path = Path();
      final rStar = radius * (pose.heartEyes ? 0.13 : 0.11);
      path.moveTo(eyeCenter.dx, eyeCenter.dy - rStar);
      path.lineTo(eyeCenter.dx + rStar * 0.4, eyeCenter.dy - rStar * 0.4);
      path.lineTo(eyeCenter.dx + rStar, eyeCenter.dy);
      path.lineTo(eyeCenter.dx + rStar * 0.4, eyeCenter.dy + rStar * 0.4);
      path.lineTo(eyeCenter.dx, eyeCenter.dy + rStar);
      path.lineTo(eyeCenter.dx - rStar * 0.4, eyeCenter.dy + rStar * 0.4);
      path.lineTo(eyeCenter.dx - rStar, eyeCenter.dy);
      path.lineTo(eyeCenter.dx - rStar * 0.4, eyeCenter.dy - rStar * 0.4);
      path.close();
      holes.addPath(path, Offset.zero);
      return;
    }
    // 常规眼：capsule 孔洞，倾斜 ~20°，开合改高度（眨眼 120ms 弧）
    final width = radius * 0.30;
    final height = radius * 0.34 * open;
    if (height < radius * 0.02) {
      return; // 完全闭合：眨眼底由本体渐变直接表现
    }
    final angle = 20 * math.pi / 180 * (left ? -1.0 : 1.0);
    final capsule = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset.zero, width: width, height: height),
        Radius.circular(height / 2),
      ));
    final rotated =
        capsule.transform((Matrix4.identity()..rotateZ(angle)).storage);
    holes.addPath(rotated.shift(eyeCenter), Offset.zero);
  }

  void _drawCrossedEyes(Canvas canvas, Offset center, double radius) {
    // error 态 x x 眼：在挖洞之上以 ink-600 细线补叉（孔洞保持挖空）
    final line = Paint()
      ..color = palette.ink600
      ..strokeWidth = radius * 0.05
      ..strokeCap = StrokeCap.round;
    for (final sign in [-1.0, 1.0]) {
      final eye = center + Offset(sign * radius * 0.34, -radius * 0.10);
      final s = radius * 0.10;
      canvas.drawLine(eye - Offset(s, s), eye + Offset(s, s), line);
      canvas.drawLine(eye + Offset(-s, s), eye + Offset(s, -s), line);
    }
  }

  void _drawRingArc(Canvas canvas, double long, double short,
      {required bool back}) {
    final rect = Rect.fromCenter(center: Offset.zero, width: long * 2, height: short * 2);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = short * 0.32
      ..shader = SweepGradient(
        colors: [
          palette.aurora.withValues(alpha: back ? 0.18 : 0.55 + pose.ringGlow * 0.45),
          palette.hydrogen.withValues(alpha: back ? 0.12 : 0.35 + pose.ringGlow * 0.35),
          palette.aurora.withValues(alpha: back ? 0.18 : 0.55 + pose.ringGlow * 0.45),
        ],
      ).createShader(rect);
    // back = 上半椭圆（本体后），front = 下半椭圆（本体前）
    canvas.drawArc(rect, back ? math.pi : 0, math.pi, false, paint);
  }

  void _drawRingStars(Canvas canvas, double long, double short,
      {required bool back}) {
    // 沿环 6~9 颗微小星点缓慢公转（梦幻感核心，V2-1）
    final starPaint = Paint()..style = PaintingStyle.fill;
    final n = ringStarCount.clamp(6, 9);
    for (var i = 0; i < n; i++) {
      final angle = pose.ringSpinRad + 2 * math.pi * i / n;
      final x = math.cos(angle) * long;
      final y = math.sin(angle) * short;
      final isBack = math.sin(angle) < 0;
      if (isBack != back) continue;
      final spark = pose.sparkIntensity > 0.01 && i % 2 == 0;
      starPaint.color = spark
          ? palette.molten.withValues(alpha: 0.6 + 0.4 * pose.sparkIntensity)
          : palette.aurora.withValues(alpha: 0.75);
      canvas.drawCircle(Offset(x, y), spark ? 2.2 : 1.4, starPaint);
    }
  }

  @override
  bool shouldRepaint(StarlingPainter oldDelegate) =>
      oldDelegate.pose != pose || oldDelegate.palette != palette;
}
