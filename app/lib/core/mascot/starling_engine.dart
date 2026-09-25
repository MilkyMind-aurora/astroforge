// 星仔纯函数引擎（星仔规格 V2 修订章——bloub 式 sample(t)，无框架无时钟依赖：
// 暂停/恢复/跳转任意时刻得到同一画面；golden test frozenAt 单帧断言）。
//
// 形态常数（V2-1 定稿，几何推导值，资产定稿后逐帧测量回填）：
// - 本体：近正圆星体（径向偏差 <0.7% 才有正圆观感——呼吸只做 1.00~1.03）；
// - 星环：椭圆环带 长轴 1.8×本体直径 / 短轴 0.5× / 倾角 -12°（error 塌落 -15°）；
// - 眼睛：遮罩挖洞，倾斜 ~20°（bloub 26° 的浪漫化取值）；
// - 缓动 = 指数 ease-out，身体永不 overshoot（过冲只允许发生在环与粒子）；
// - 生命感 = 眨眼 + 视线漂移，休息时不漂浮（bloub 反直觉发现：星球悬停本就静止）。

import 'dart:math' as math;
import 'dart:ui';

/// 业务态 7（V1 §一 语义不变；V2-3 层 1）。
enum StarlingState { idle, thinking, speaking, happy, error, sleeping, celebrate }

/// 表情基元（V2-3 层 2，可叠加于静息类业务态）。
enum StarlingPrimitive {
  none,
  blink, // 双眼孔洞闭合 120ms（idle 期 6~14s 随机，由宿主调度 blinkT）
  wink, // 单眼闭合 400ms（语录卡弹出）
  starEyes, // 双眼变 ✦（星等成就/流水线全通）
  heartEyes, // 双眼变 ♥（深夜极光爆发，每日 ≤2 次由宿主计数）
  blush, // 双颊 aurora@20% 圆晕（同 heart-eyes 或戳星仔 3 次）
  dizzy, // 双眼 spiral（连环失败 ≥3 次）
}

/// 单帧几何（纯数据，painter 只消费不推算）。
class StarlingPose {
  const StarlingPose({
    required this.bodyScaleX,
    required this.bodyScaleY,
    required this.eyeOpennessL,
    required this.eyeOpennessR,
    required this.gazeOffset,
    required this.ringTiltDeg,
    required this.ringSpinRad,
    required this.ringGlow,
    required this.mouthOpen,
    required this.blushAlpha,
    required this.sparkIntensity,
    required this.crossedEyes,
    required this.starEyes,
    required this.heartEyes,
    required this.zParticlePhase,
  });

  final double bodyScaleX;
  final double bodyScaleY;
  final double eyeOpennessL;
  final double eyeOpennessR;
  final Offset gazeOffset; // ±2dp 视线漂移（星仔规格 gaze_x/y）
  final double ringTiltDeg; // -12 基准；error 塌落再 -15
  final double ringSpinRad; // thinking 星环旋转相位（1.2s/圈）
  final double ringGlow; // celebrate 整环点亮 0..1
  final double mouthOpen; // speaking 嘴部开合 0..1（idle 无嘴）
  final double blushAlpha; // 0..1
  final double sparkIntensity; // happy/celebrate 环上迸熔金火星 0..1
  final bool crossedEyes; // error 眼 x x
  final bool starEyes;
  final bool heartEyes;
  final double zParticlePhase; // sleeping z 粒子相位（4s 慢呼吸同步）

  static const idle = StarlingPose(
    bodyScaleX: 1, bodyScaleY: 1,
    eyeOpennessL: 1, eyeOpennessR: 1,
    gazeOffset: Offset.zero,
    ringTiltDeg: -12, ringSpinRad: 0, ringGlow: 0,
    mouthOpen: 0, blushAlpha: 0, sparkIntensity: 0,
    crossedEyes: false, starEyes: false, heartEyes: false,
    zParticlePhase: 0,
  );
}

/// 指数 ease-out（bloub 实证纪律：身体永不 overshoot）。
double _easeOut(double t) => 1 - math.pow(1 - t.clamp(0.0, 1.0), 3).toDouble();

/// 纯函数采样：同一组入参必得同一 StarlingPose（frozenAt 单帧断言友好）。
StarlingPose sampleStarling({
  required StarlingState state,
  required double t, // 业务态内相位（秒；golden 传冻结值）
  StarlingPrimitive primitive = StarlingPrimitive.none,
  double primitiveT = 0, // 基元内进度 0..1
  double blinkT = 0, // 眨眼进度 0..1（宿主按 6~14s 调度、120ms 窗口内线性）
  Offset gaze = Offset.zero, // 宿主视线目标（±2dp 内）
}) {
  double bodyX = 1, bodyY = 1;
  double ringTilt = -12, ringSpin = 0, ringGlow = 0;
  double mouth = 0, blush = 0, spark = 0, zPhase = 0;
  var crossed = false;
  var starEyes = primitive == StarlingPrimitive.starEyes;
  final heartEyes = primitive == StarlingPrimitive.heartEyes;
  var eyesOpen = 1.0;

  switch (state) {
    case StarlingState.idle:
    case StarlingState.sleeping:
      // 休息时不漂浮：sleeping 仅 4s 慢呼吸（V1 sleeping 行为保留）
      if (state == StarlingState.sleeping) {
        final breath = math.sin(2 * math.pi * t / 4.0);
        bodyY = 1 + 0.015 * breath;
        bodyX = 1 - 0.010 * breath; // 挤压守恒，无 overshoot
        zPhase = (t / 2.0) % 1.0; // z 每 2s 飘一枚
        eyesOpen = 0.0; // 眼 ‿ ‿（闭眼弧线由 painter 处理）
      }
    case StarlingState.thinking:
      // 低头看锤柄 + 头顶 nebula 星环旋转（1.2s）+ 眼收窄
      ringSpin = 2 * math.pi * t / 1.2;
      eyesOpen = 0.6;
      bodyX = 1;
      bodyY = 1 - 0.02 * _easeOut((t % 1.2) / 1.2); // 轻微点头无过冲
    case StarlingState.speaking:
      // 嘴部开合 0.8s + 微前倾 2dp（缩放表达，禁位移过冲）
      mouth = (math.sin(2 * math.pi * t / 0.8) * 0.5 + 0.5) *
          _easeOut((t % 0.8) / 0.8);
      bodyX = 1 + 0.012;
    case StarlingState.happy:
      // 举锤迸火星（一次性由宿主控制时长）；环微倾过冲允许（环可弹）
      spark = _easeOut(1 - (t % 1.2) / 1.2);
      ringTilt = -12 + 6 * spark;
      starEyes = true;
      ringGlow = 0.4 * spark;
    case StarlingState.error:
      // squash 0.96 + 星环塌落 15° + 眼 x x（错误语义留给任务卡，本体不用红色）
      bodyX = 1.02;
      bodyY = 0.96;
      ringTilt = -12 - 15;
      crossed = true;
      eyesOpen = 1;
    case StarlingState.celebrate:
      ringGlow = 1;
      spark = _easeOut(1 - (t % 1.6) / 1.6);
      ringTilt = -12 + 10 * math.sin(2 * math.pi * t / 1.6);
      starEyes = true;
  }

  // ---- 表情基元叠加（仅静息类业务态生效，V2-3）----
  final restful =
      state == StarlingState.idle || state == StarlingState.sleeping;
  double openL = eyesOpen, openR = eyesOpen;
  if (primitive == StarlingPrimitive.blink && restful && state == StarlingState.idle) {
    final close = math.sin(math.pi * blinkT.clamp(0.0, 1.0)); // 120ms 闭合弧
    openL = eyesOpen * (1 - close);
    openR = openL;
  } else if (primitive == StarlingPrimitive.wink && restful) {
    final close = math.sin(math.pi * primitiveT.clamp(0.0, 1.0));
    openR = eyesOpen * (1 - close); // 单眼闭合 400ms + 环微倾
    ringTilt += 2 * close;
  } else if (primitive == StarlingPrimitive.blush && restful) {
    blush = math.sin(math.pi * primitiveT.clamp(0.0, 1.0));
  } else if (!restful) {
    // 静息类才叠加基元；happy/celebrate 已带 starEyes，error 恒 x x
    starEyes = starEyes || (primitive == StarlingPrimitive.starEyes);
  }

  // 视线漂移限幅 ±2dp（painter 空间；宿主传入前已限幅，这里双保险）
  final gazeClamped = Offset(
    gaze.dx.clamp(-2.0, 2.0),
    gaze.dy.clamp(-2.0, 2.0),
  );

  return StarlingPose(
    bodyScaleX: bodyX,
    bodyScaleY: bodyY,
    eyeOpennessL: openL,
    eyeOpennessR: openR,
    gazeOffset: gazeClamped,
    ringTiltDeg: ringTilt,
    ringSpinRad: ringSpin,
    ringGlow: ringGlow,
    mouthOpen: mouth,
    blushAlpha: blush,
    sparkIntensity: spark,
    crossedEyes: crossed,
    starEyes: starEyes,
    heartEyes: heartEyes,
    zParticlePhase: zPhase,
  );
}

/// 眨眼调度表（宿主侧；6~14s 随机——引擎本体保持纯函数）。
class BlinkScheduler {
  BlinkScheduler({math.Random? random}) : _random = random ?? math.Random();

  final math.Random _random;
  double _nextBlinkAt = 6;

  /// 返回当前 blinkT（0 = 未在眨眼；(0,1) = 120ms 窗口内进度）。
  double tick(double seconds) {
    const windowS = 0.12;
    if (seconds >= _nextBlinkAt) {
      final progress = (seconds - _nextBlinkAt) / windowS;
      if (progress >= 1) {
        _nextBlinkAt = seconds + 6 + _random.nextDouble() * 8;
        return 0;
      }
      return progress;
    }
    return 0;
  }
}
