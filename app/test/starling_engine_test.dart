// 星仔纯函数引擎测试（星仔规格 V2-2：sample(t) 同入参必同画面；frozenAt 断言）。
import 'dart:math' as math;

import 'package:astroforge/core/mascot/starling_engine.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('sampleStarling 纯函数性', () {
    test('同一入参两次采样得到完全一致的姿态（frozenAt 单帧断言基础）', () {
      final a = sampleStarling(state: StarlingState.idle, t: 3.3);
      final b = sampleStarling(state: StarlingState.idle, t: 3.3);
      expect(a.bodyScaleX, b.bodyScaleX);
      expect(a.bodyScaleY, b.bodyScaleY);
      expect(a.eyeOpennessL, b.eyeOpennessL);
      expect(a.ringTiltDeg, b.ringTiltDeg);
      expect(a.ringSpinRad, b.ringSpinRad);
      expect(a.mouthOpen, b.mouthOpen);
    });

    test('休息态不漂浮（bloub 纪律）：idle 本体缩放恒 1', () {
      for (final t in [0.0, 1.7, 3.3, 7.9]) {
        final pose = sampleStarling(state: StarlingState.idle, t: t);
        expect(pose.bodyScaleX, 1.0);
        expect(pose.bodyScaleY, 1.0);
      }
    });

    test('sleeping 4s 慢呼吸：本体有起伏且无 overshoot（≤1.03）', () {
      final pose = sampleStarling(state: StarlingState.sleeping, t: 1.0);
      expect(pose.bodyScaleY, greaterThan(1.0));
      final maxSample = [
        for (var i = 0; i < 40; i++)
          sampleStarling(state: StarlingState.sleeping, t: i * 0.1).bodyScaleY,
      ].reduce((a, b) => a > b ? a : b);
      expect(maxSample, lessThanOrEqualTo(1.03));
    });

    test('眨眼基元：blinkT=0.5 双眼完全闭合（120ms 弧中点）', () {
      final pose = sampleStarling(
        state: StarlingState.idle,
        t: 0,
        primitive: StarlingPrimitive.blink,
        blinkT: 0.5,
      );
      expect(pose.eyeOpennessL, lessThan(0.05));
      expect(pose.eyeOpennessR, lessThan(0.05));
    });

    test('thinking：星环以 1.2s 周期旋转 + 眼收窄', () {
      final t0 = sampleStarling(state: StarlingState.thinking, t: 0);
      final t1 = sampleStarling(state: StarlingState.thinking, t: 0.3);
      expect(t1.ringSpinRad, greaterThan(t0.ringSpinRad));
      expect(t0.eyeOpennessL, 0.6);
      // 1.2s 整周期相位对 2π 等价（浮点容差）
      final full = sampleStarling(state: StarlingState.thinking, t: 1.2);
      final twoPi = 2 * math.pi;
      final delta = (full.ringSpinRad - t0.ringSpinRad) % twoPi;
      expect(delta, closeTo(0, 1e-6));
    });

    test('error：squash 0.96 + 星环塌落 -27° + x x 眼', () {
      final pose = sampleStarling(state: StarlingState.error, t: 0);
      expect(pose.bodyScaleY, 0.96);
      expect(pose.ringTiltDeg, -27);
      expect(pose.crossedEyes, isTrue);
    });

    test('celebrate：整环点亮', () {
      final pose = sampleStarling(state: StarlingState.celebrate, t: 0.2);
      expect(pose.ringGlow, 1.0);
    });

    test('speaking：嘴部有开合且身体不过冲（缩放 ≤1.02）', () {
      var sawOpen = false;
      for (var i = 0; i < 20; i++) {
        final pose = sampleStarling(state: StarlingState.speaking, t: i * 0.1);
        if (pose.mouthOpen > 0.3) sawOpen = true;
        expect(pose.bodyScaleX, lessThanOrEqualTo(1.02));
      }
      expect(sawOpen, isTrue);
    });

    test('gaze 限幅 ±2dp（引擎双保险）', () {
      final pose = sampleStarling(
        state: StarlingState.idle,
        t: 0,
        gaze: const Offset(9, -9),
      );
      expect(pose.gazeOffset.dx, 2.0);
      expect(pose.gazeOffset.dy, -2.0);
    });
  });

  group('BlinkScheduler', () {
    test('6~14s 随机间隔调度，120ms 窗口内返回进度', () {
      final scheduler = BlinkScheduler();
      // 首次眨眼不早于 6s
      for (var t = 0.0; t < 5.9; t += 0.01) {
        expect(scheduler.tick(t), 0.0);
      }
      // 120ms 窗口内必有进度（若恰在窗口中）
      var sawProgress = false;
      for (var t = 6.0; t < 14.2; t += 0.01) {
        if (scheduler.tick(t) > 0) {
          sawProgress = true;
          break;
        }
      }
      expect(sawProgress, isTrue);
    });
  });
}
