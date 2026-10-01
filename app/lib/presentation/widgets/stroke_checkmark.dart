import 'package:flutter/material.dart';

/// 成功勾选一笔画（§1.8 #15）：PathMetric 沿勾形路径 0→全长描画 260ms。
/// reduced-motion 直接整段呈现（降级表：瞬时到位）。
class StrokeCheckmark extends StatefulWidget {
  const StrokeCheckmark({
    required this.color,
    this.size = 12,
    this.strokeWidth = 2,
    this.durationMs = 260,
    this.playKey = 0,
    super.key,
  });

  final Color color;

  /// 画布边长（dp）——路径按此归一化。
  final double size;
  final double strokeWidth;

  /// 描画时长（规格 #15：260ms，转场档）。
  final int durationMs;

  /// 变更此值即重播一笔画（0=挂载时播一次）。
  final int playKey;

  @override
  State<StrokeCheckmark> createState() => _StrokeCheckmarkState();
}

class _StrokeCheckmarkState extends State<StrokeCheckmark>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  bool _reduced = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: widget.durationMs),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
    _start();
  }

  @override
  void didUpdateWidget(StrokeCheckmark oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.playKey != widget.playKey ||
        oldWidget.size != widget.size) {
      _start();
    }
  }

  void _start() {
    if (_reduced) {
      _controller.value = 1.0;
      return;
    }
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// 勾形路径：短臂 30%→中腰 55%，长臂 55%→100%（一笔连贯）。
  static Path checkPath(double size) {
    return Path()
      ..moveTo(size * 0.22, size * 0.54)
      ..lineTo(size * 0.42, size * 0.74)
      ..lineTo(size * 0.78, size * 0.30);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return CustomPaint(
          size: Size.square(widget.size),
          painter: _CheckPainter(
            color: widget.color,
            strokeWidth: widget.strokeWidth,
            t: _controller.value,
          ),
        );
      },
    );
  }
}

class _CheckPainter extends CustomPainter {
  const _CheckPainter({
    required this.color,
    required this.strokeWidth,
    required this.t,
  });

  final Color color;
  final double strokeWidth;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final path = _StrokeCheckmarkState.checkPath(size.shortestSide);
    final metrics = path.computeMetrics().toList();
    if (metrics.isEmpty) return;
    final metric = metrics.first;
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    // 线性描画：0→t 全长（勾形一笔，禁缓动起步——260ms 内匀速走完）
    final partial = metric.extractPath(0, metric.length * t.clamp(0.0, 1.0));
    canvas.drawPath(partial, paint);
  }

  @override
  bool shouldRepaint(_CheckPainter oldDelegate) =>
      oldDelegate.t != t ||
      oldDelegate.color != color ||
      oldDelegate.strokeWidth != strokeWidth;
}

/// 供勾账表引用的路径构造（与 painter 同源，测试断言用）。
Path strokeCheckmarkPath(double size) =>
    _StrokeCheckmarkState.checkPath(size);
