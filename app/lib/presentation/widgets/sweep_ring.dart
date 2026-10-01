import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 边缘高亮跑圈（§1.8 #17-Flutter）：sweepGradient 高亮弧沿圆环匀速跑圈，
/// dur-loop 档 1.2s/圈（与 TUI boot 跑圈 4 帧×0.3s 同周期）。
/// 用途：引擎唤醒/服务拉起等「探活期唯一循环动画位」（reduced-motion：
/// 静态半圈高亮，禁循环）。
class SweepRing extends StatefulWidget {
  const SweepRing({
    required this.size,
    this.strokeWidth = 2.5,
    this.revolutions = 1.0,
    super.key,
  });

  /// 环外径（dp）。
  final double size;
  final double strokeWidth;

  /// 每秒圈数（默认 1 圈/s = 1.2s/圈的 dur-loop 同档——取整避免自造值）。
  final double revolutions;

  @override
  State<SweepRing> createState() => _SweepRingState();
}

class _SweepRingState extends State<SweepRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _spin = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200), // dur-loop：1.2s 一圈
  );
  bool _reduced = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
    if (_reduced) {
      _spin.stop();
      _spin.value = 0.25; // 静态帧：高亮弧停在右上（可感知进行态）
    } else if (!_spin.isAnimating) {
      _spin.repeat();
    }
  }

  @override
  void didUpdateWidget(SweepRing oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_reduced) return;
    if (!_spin.isAnimating) _spin.repeat();
  }

  @override
  void dispose() {
    _spin.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final dark = AstroPaletteScope.darkProgressOf(context) >= 0.5;
    return AnimatedBuilder(
      animation: _spin,
      builder: (context, _) => CustomPaint(
        size: Size.square(widget.size),
        painter: _SweepRingPainter(
          strokeWidth: widget.strokeWidth,
          rotation: _spin.value * 2 * math.pi,
          colors: dark ? AstroGalaxy.darkStops : AstroGalaxy.lightStops,
          track: palette.container,
        ),
      ),
    );
  }
}

class _SweepRingPainter extends CustomPainter {
  const _SweepRingPainter({
    required this.strokeWidth,
    required this.rotation,
    required this.colors,
    required this.track,
  });

  final double strokeWidth;
  final double rotation;
  final List<Color> colors;
  final Color track;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (size.shortestSide - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);
    // 底轨：container 实环（层级靠明度）
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..color = track,
    );
    // 高亮弧：galaxy 三停驻彗尾（亮头 0→0.18 圈，0.34 处淡出成尾迹），
    // 随 rotation 匀速跑圈
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: 0,
        endAngle: 2 * math.pi,
        stops: const [0.0, 0.09, 0.18, 0.34],
        colors: [
          colors[0],
          colors[1],
          colors[2],
          colors[2].withValues(alpha: 0),
        ],
        transform: GradientRotation(-math.pi / 2 + rotation),
      ).createShader(rect);
    canvas.drawArc(rect, 0, 2 * math.pi, false, paint);
  }

  @override
  bool shouldRepaint(_SweepRingPainter oldDelegate) =>
      oldDelegate.rotation != rotation || oldDelegate.track != track;
}

/// 供测试断言的周期常量（dur-loop 档：1.2s 一圈）。
const int sweepRingPeriodMs = 1200;
