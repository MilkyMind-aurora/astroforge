import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'dart:ui' show FragmentProgram, FragmentShader;

import '../design/design.dart';
import 'star_seed.dart';

/// 星野背景（§1.5 / 星空设计系统规格 §四「星野」/ MF4 壳层）：
/// - 生产路径：shaders/starfield.frag（uTime/uSeed/uDensity/uAlphaMax/uDriftAmp/
///   uMeteorT 参数化；uSeed = seed.json 的 seed——同种子必同星象，禁每帧随机）；
/// - 降级路径：Canvas painter 直接绘 seed.json 坐标列表（测试/无 shader 环境；
///   golden test 冻结 uTime=0 的等价物）；
/// - 失焦暂停：AppLifecycleState 非 resumed 时冻结星野时钟；
/// - 弹层打开（ModalRoute 非 current）时流星暂停——活光 ≤1 让位（规格 §五）；
/// - 帧率降级纪律（uDensity=0）由 tokens.starfield.degrade_rule 声明，本期
///   未接帧率采样器，如实不伪造（见 milestone notes）。
class StarfieldView extends ConsumerStatefulWidget {
  const StarfieldView({super.key, this.forceCanvas = false});

  /// 测试/金测路径：跳过 FragmentProgram（确定性 Canvas 渲染）。
  final bool forceCanvas;

  @override
  ConsumerState<StarfieldView> createState() => _StarfieldViewState();
}

class _StarfieldViewState extends ConsumerState<StarfieldView>
    with WidgetsBindingObserver, SingleTickerProviderStateMixin {
  StarSeed? _seed;
  FragmentShader? _shader;
  late final Ticker _ticker;
  double _seconds = 0;
  bool _focused = true;
  bool _reduced = false;
  double _lastMeteorRoll = 0;
  double _meteorStart = -1; // 星野时钟上的流星起始秒；<0 无进行中流星
  final math.Random _meteorDice = math.Random();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _ticker = createTicker(_onTick)..start();
    _load();
  }

  Future<void> _load() async {
    // 星野首帧可后挂（§5.8：首帧 ≤1.5s）——资产加载不阻塞首帧。
    StarSeed? seed;
    try {
      seed = await StarSeed.loadAsset();
    } catch (_) {
      seed = null; // 资产缺失 → 空星野（不阻塞内容）
    }
    if (!mounted) return;
    setState(() => _seed = seed);
    if (widget.forceCanvas) return;
    try {
      final program =
          await FragmentProgram.fromAsset('shaders/starfield.frag');
      if (!mounted) return;
      setState(() => _shader = program.fragmentShader());
    } catch (e) {
      // shader 编译/加载失败 → Canvas 降级（禁黑屏）
      debugPrint('starfield shader unavailable, fallback to canvas: $e');
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
  }

  void _onTick(Duration elapsed) {
    if (!mounted) return;
    if (!_focused || _reduced) {
      return; // 失焦/reduced-motion：时钟冻结，保持上一帧（禁逐帧空转）
    }
    final now = elapsed.inMicroseconds / 1e6;
    _seconds = now;
    _advanceMeteor(now);
    setState(() {});
  }

  void _advanceMeteor(double now) {
    final modalOpen = ModalRoute.of(context)?.isCurrent == false;
    if (_meteorStart >= 0) {
      final t = (_seconds - _meteorStart) * 1000 / AstroStarfield.meteorDurationMs;
      if (t > 1) {
        _meteorStart = -1;
        _lastMeteorRoll = now;
      }
      return;
    }
    // E1 流星：前台每 ≥120s 掷 25%（期望 ~8 分钟一颗）；弹层打开时暂停
    if (modalOpen) return;
    if (now - _lastMeteorRoll >= AstroStarfield.meteorIntervalS) {
      _lastMeteorRoll = now;
      if (_meteorDice.nextDouble() < 0.25) {
        _meteorStart = now;
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    setState(() => _focused = state == AppLifecycleState.resumed);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final darkProgress = AstroPaletteScope.darkProgressOf(context);
    final seed = _seed;
    final reducedMotion = _reduced;
    final size = MediaQuery.sizeOf(context);
    final t = reducedMotion ? 0.0 : _seconds; // reduced-motion：星野完全静态

    if (seed == null) {
      return const SizedBox.expand();
    }

    // 星野参数全部来自 tokens.g.dart；alpha 昼档减半（规格 §四）
    final isDark = darkProgress >= 0.5;
    final alphaMax = isDark
        ? AstroStarfield.alphaSteps.last
        : AstroStarfield.alphaSteps.last / 2;

    if (!reducedMotion && _shader != null) {
      final meteorT = _meteorStart >= 0
          ? ((t - _meteorStart) * 1000 / AstroStarfield.meteorDurationMs)
              .clamp(0.0, 1.0)
          : -1.0;
      return _ShaderStarfield(
        shader: _shader!,
        seed: seed,
        time: t,
        alphaMax: alphaMax,
        starColor: palette.ink600,
        driftAmp: AstroStarfield.driftDp / size.shortestSide,
        meteorT: meteorT,
      );
    }
    // Canvas 降级：seed.json 坐标直绘；reduced-motion 时 t=0（金测等价）
    return CustomPaint(
      painter: StarfieldCanvasPainter(
        seed: seed,
        palette: palette,
        time: t,
        alphaMax: alphaMax,
      ),
      size: Size.infinite,
    );
  }
}

class _ShaderStarfield extends StatelessWidget {
  const _ShaderStarfield({
    required this.shader,
    required this.seed,
    required this.time,
    required this.alphaMax,
    required this.starColor,
    required this.driftAmp,
    required this.meteorT,
  });

  final FragmentShader shader;
  final StarSeed seed;
  final double time;
  final double alphaMax;
  final Color starColor;
  final double driftAmp;
  final double meteorT;

  @override
  Widget build(BuildContext context) {
    // uniform 槽位与 starfield.frag 声明一一对应（uSize/uTime/uSeed/uDensity/
    // uAlphaMax/uDriftAmp/uMeteorT/uStarColor）。
    final size = MediaQuery.sizeOf(context);
    shader.setFloat(0, size.width);
    shader.setFloat(1, size.height);
    shader.setFloat(2, time);
    shader.setFloat(3, seed.seed.toDouble());
    shader.setFloat(4, seed.densityMax.toDouble());
    shader.setFloat(5, alphaMax);
    shader.setFloat(6, driftAmp);
    shader.setFloat(7, meteorT);
    shader.setFloat(8, starColor.r);
    shader.setFloat(9, starColor.g);
    shader.setFloat(10, starColor.b);
    return SizedBox.expand(
      child: CustomPaint(painter: _ShaderPainter(shader)),
    );
  }
}

class _ShaderPainter extends CustomPainter {
  const _ShaderPainter(this.shader);

  final FragmentShader shader;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
  }

  @override
  bool shouldRepaint(_ShaderPainter oldDelegate) => true;
}

/// Canvas 降级 painter：seed.json 预生成坐标（避免每帧随机），
/// 亮度 alpha 三档 0.04/0.08/0.12（昼档减半），±2dp/4s 缓漂。
class StarfieldCanvasPainter extends CustomPainter {
  const StarfieldCanvasPainter({
    required this.seed,
    required this.palette,
    required this.time,
    required this.alphaMax,
  });

  final StarSeed seed;
  final AstroPalette palette;
  final double time;
  final double alphaMax;

  @override
  void paint(Canvas canvas, Size size) {
    final starPaint = Paint()..style = PaintingStyle.fill;
    for (final star in seed.stars) {
      final dx = math.sin(
              2 * math.pi * time / AstroStarfield.driftPeriodS + star.phase) *
          AstroStarfield.driftDp;
      final dy = math.cos(
              2 * math.pi * time / AstroStarfield.driftPeriodS + star.phase * 1.3) *
          AstroStarfield.driftDp;
      final tierAlpha = switch (star.tier) {
        0 => AstroStarfield.alphaSteps[0] / AstroStarfield.alphaSteps.last,
        1 => AstroStarfield.alphaSteps[1] / AstroStarfield.alphaSteps.last,
        _ => 1.0,
      };
      starPaint.color =
          palette.ink600.withValues(alpha: (alphaMax * tierAlpha).clamp(0.0, 1.0));
      final radius = AstroStarfield.sizeSteps[star.tier.clamp(0, 2)] / 2;
      canvas.drawCircle(
        Offset(star.x * size.width + dx, star.y * size.height + dy),
        radius,
        starPaint,
      );
    }
  }

  @override
  bool shouldRepaint(StarfieldCanvasPainter oldDelegate) =>
      oldDelegate.time != time ||
      oldDelegate.palette != palette ||
      oldDelegate.alphaMax != alphaMax;
}
