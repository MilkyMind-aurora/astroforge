// ETA 估算工具单测（终审 M5）：progress 速率 / 步骤均耗时 / 字节口径 /
// 长时档闸门 / 文案格式——纯函数全覆盖。
import 'package:flutter_test/flutter_test.dart';

import 'package:astroforge/core/eta/eta_estimator.dart';

void main() {
  final now = DateTime(2026, 10, 1, 12, 0, 0);

  group('estimateTaskEta（progress 速率）', () {
    test('匀速外推：50% 用时 60s → 剩余 60s', () {
      final eta = estimateTaskEta(
        progress: 50,
        startedAt: now.subtract(const Duration(seconds: 60)),
        now: now,
      );
      expect(eta, const Duration(seconds: 60));
    });

    test('25% 用时 40s → 剩余 120s', () {
      final eta = estimateTaskEta(
        progress: 25,
        startedAt: now.subtract(const Duration(seconds: 40)),
        now: now,
      );
      expect(eta, const Duration(seconds: 120));
    });

    test('progress=0 无外推依据 → null（禁伪造）', () {
      final eta = estimateTaskEta(
        progress: 0,
        startedAt: now.subtract(const Duration(seconds: 60)),
        now: now,
      );
      expect(eta, isNull);
    });

    test('无 startedAt → null', () {
      expect(
        estimateTaskEta(progress: 50, startedAt: null, now: now),
        isNull,
      );
    });

    test('progress 越界 → null', () {
      expect(
        estimateTaskEta(
          progress: 120,
          startedAt: now.subtract(const Duration(seconds: 60)),
          now: now,
        ),
        isNull,
      );
    });
  });

  group('estimateTaskEta（步骤均耗时）', () {
    test('2 步完成均 30s、剩 2 步 → 60s（>progress 速率时取大者）', () {
      final eta = estimateTaskEta(
        progress: 50, // 速率口径：用时 60s → 剩余 60s
        startedAt: now.subtract(const Duration(seconds: 60)),
        now: now,
        steps: [
          {
            'status': 'success',
            'started_at': now.subtract(const Duration(seconds: 60)).toIso8601String(),
            'finished_at':
                now.subtract(const Duration(seconds: 30)).toIso8601String(),
          },
          {
            'status': 'success',
            'started_at':
                now.subtract(const Duration(seconds: 30)).toIso8601String(),
            'finished_at': now.toIso8601String(),
          },
          {'status': 'running'},
          {'status': 'pending'},
        ],
      );
      // 步骤口径 2×30s=60s 与速率口径同值 → 60s
      expect(eta, const Duration(seconds: 60));
    });

    test('步骤均耗时大于速率口径时取大者（保守承诺）', () {
      final eta = estimateTaskEta(
        progress: 80, // 速率口径：用时 100s → 剩余 25s
        startedAt: now.subtract(const Duration(seconds: 100)),
        now: now,
        steps: [
          {
            'status': 'success',
            'started_at': now.subtract(const Duration(seconds: 100)).toIso8601String(),
            'finished_at': now.subtract(const Duration(seconds: 20)).toIso8601String(),
          },
          {'status': 'running'}, // 1 步未完，均耗时 80s → 80s
        ],
      );
      expect(eta, const Duration(seconds: 80));
    });

    test('失败步骤不计入剩余（任务已停）', () {
      final eta = estimateTaskEta(
        progress: 30,
        startedAt: now.subtract(const Duration(seconds: 30)),
        now: now,
        steps: [
          {'status': 'success'},
          {'status': 'failed'},
          {'status': 'pending'},
        ],
      );
      // 无任何步骤耗时数据 → 仅速率口径：30% 用时 30s → 70s
      expect(eta, const Duration(seconds: 70));
    });
  });

  group('estimateBytesEta（模型加载·字节口径）', () {
    test('1GB 已载 512MB 用时 10s → 剩余 ~10s', () {
      final eta = estimateBytesEta(
        totalBytes: 1024 * 1024 * 1024,
        loadedBytes: 512 * 1024 * 1024,
        elapsed: const Duration(seconds: 10),
      );
      expect(eta!.inMilliseconds, closeTo(10000, 1));
    });

    test('无进度（loaded=0）→ null', () {
      expect(
        estimateBytesEta(
          totalBytes: 1000,
          loadedBytes: 0,
          elapsed: const Duration(seconds: 10),
        ),
        isNull,
      );
    });

    test('已载完（loaded>=total）→ null（无剩余）', () {
      expect(
        estimateBytesEta(
          totalBytes: 1000,
          loadedBytes: 1000,
          elapsed: const Duration(seconds: 10),
        ),
        isNull,
      );
    });

    test('elapsed=0 → null', () {
      expect(
        estimateBytesEta(
          totalBytes: 1000,
          loadedBytes: 100,
          elapsed: Duration.zero,
        ),
        isNull,
      );
    });
  });

  group('formatEta / shouldShowEta（长时档闸门）', () {
    test('秒级：45s → ≈45s', () {
      expect(formatEta(const Duration(seconds: 45)), '≈45s');
    });

    test('分级：130s → ≈2m10s', () {
      expect(formatEta(const Duration(seconds: 130)), '≈2m10s');
    });

    test('时分：3900s → ≈1h05m', () {
      expect(formatEta(const Duration(seconds: 3900)), '≈1h05m');
    });

    test('无界：>6h → >6h', () {
      expect(formatEta(const Duration(hours: 7)), '>6h');
    });

    test('≤10s 瞬时档不显示（防闪烁）', () {
      expect(shouldShowEta(const Duration(seconds: 10)), isFalse);
      expect(shouldShowEta(const Duration(seconds: 11)), isTrue);
    });

    test('null 不显示', () {
      expect(shouldShowEta(null), isFalse);
    });

    test('>6h 仍显示（报「>6h」无界值）', () {
      expect(shouldShowEta(const Duration(hours: 7)), isTrue);
    });
  });
}
