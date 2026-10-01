// ============================================================
// ETA 估算工具（终审 M5：长时档「预计剩余时长」唯一计算处）
// - 任务：progress 速率折算为主、步骤均耗时折算为辅，两者同可得时取
//   大者（保守承诺——宁可晚报不虚报）；
// - 模型加载：已加载字节 / 总字节 + 已耗时线性外推（数据源就绪即接线；
//   当前引擎 /v1/model/load 无 loaded_bytes 回传，见文件尾承接说明）；
// - 长时档红线：估算剩余 ≤10s 属瞬时档不显示（防短任务 ETA 闪烁），
//   上限 6h 视为无界（按日级任务不再报秒级数字）。
// 纯函数无 I/O：now/bytes 全部显式入参，可测可复现。
// ============================================================

/// 长时档阈值（>10s 才显示 ETA——瞬时档禁抖动标签）。
const int etaLongTierThresholdS = 10;

/// 折算上限：超过按无界处理（formatEta 输出「>6h」）。
const int etaMaxHorizonS = 6 * 3600;

/// 任务 ETA：按 progress 速率与步骤均耗时折算剩余时长。
///
/// [progress] 0..100；[startedAt] 为任务开始时刻（null=未开始，无估算依据）；
/// [steps] 为服务端步骤字典（status/started_at/finished_at），可选。
/// 返回 null = 数据不足（progress=0 且无步骤耗时——禁伪造）。
Duration? estimateTaskEta({
  required int progress,
  required DateTime? startedAt,
  required DateTime now,
  List<dynamic> steps = const [],
}) {
  if (startedAt == null) return null;
  final elapsedMs = now.difference(startedAt).inMilliseconds;
  if (elapsedMs <= 0) return null;
  if (progress < 0 || progress > 100) return null;

  // ① progress 速率：平均速率外推剩余（匀速假设——估算口径如实在 UI 标注）
  final progressEtaMs = progress > 0
      ? elapsedMs * (100 - progress) / progress
      : null;

  // ② 步骤均耗时：已完成步骤平均时长 × 未完成步骤数（含运行中步骤整段）
  Duration? stepsEta;
  if (steps.isNotEmpty) {
    final doneDurationsMs = <int>[];
    var remaining = 0;
    for (final raw in steps) {
      if (raw is! Map) continue;
      final status = raw['status'] as String?;
      final start = DateTime.tryParse(raw['started_at'] as String? ?? '');
      final finish = DateTime.tryParse(raw['finished_at'] as String? ?? '');
      if (status == 'success') {
        if (start != null && finish != null) {
          final ms = finish.difference(start).inMilliseconds;
          if (ms > 0) doneDurationsMs.add(ms);
        }
      } else if (status == 'running' || status == 'pending') {
        remaining += 1;
      }
    }
    if (doneDurationsMs.isNotEmpty && remaining > 0) {
      final avgMs = doneDurationsMs.fold<int>(0, (a, b) => a + b) ~/
          doneDurationsMs.length;
      stepsEta = Duration(milliseconds: avgMs * remaining);
    }
  }

  // ③ 取可得者中的大者（保守承诺）
  final progressEta =
      progressEtaMs == null ? null : Duration(milliseconds: progressEtaMs.round());
  final candidates = [
    ?progressEta,
    ?stepsEta,
  ];
  if (candidates.isEmpty) return null;
  final eta = candidates.reduce((a, b) => a >= b ? a : b);
  if (eta.inMilliseconds <= 0) return null;
  return eta;
}

/// 字节级 ETA（模型加载等线性下载/装载）：已耗时 × 剩余/已装载。
/// loaded<=0 或 >=total 或 elapsed<=0 → null（无外推依据，禁伪造）。
Duration? estimateBytesEta({
  required int totalBytes,
  required int loadedBytes,
  required Duration elapsed,
}) {
  if (totalBytes <= 0 || loadedBytes <= 0 || loadedBytes >= totalBytes) {
    return null;
  }
  if (elapsed.inMilliseconds <= 0) return null;
  final remainingMs =
      elapsed.inMilliseconds * (totalBytes - loadedBytes) / loadedBytes;
  if (remainingMs <= 0) return null;
  return Duration(milliseconds: remainingMs.round());
}

/// ETA 文案（mono 等宽由调用方字体承担）：≈45s / ≈2m10s / ≈1h05m / >6h。
String formatEta(Duration eta) {
  final seconds = eta.inSeconds;
  if (seconds > etaMaxHorizonS) return '>6h';
  if (seconds < 60) return '≈${seconds}s';
  if (seconds < 3600) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '≈${m}m${s.toString().padLeft(2, '0')}s';
  }
  final h = seconds ~/ 3600;
  final m = (seconds % 3600) ~/ 60;
  return '≈${h}h${m.toString().padLeft(2, '0')}m';
}

/// 长时档闸门：仅剩余 >10s 显示（瞬时档禁闪烁）；无界（>6h）也显示「>6h」。
bool shouldShowEta(Duration? eta) =>
    eta != null && eta.inSeconds > etaLongTierThresholdS;

// ---- 承接说明（诚实登记）----
// 「模型加载按字节与耗时」：estimateBytesEta 已实现并有单测覆盖，但服务端
// modules/ai_engine /v1/model/load 目前只回 {"current_model"}，无
// loaded_bytes/total_bytes 进度。首页点火卡（引擎唤醒·模型装载）因此暂以
// 文档化冷启动经验值（≈30s，见 home_page._wakeEngine 注释与 §5.1 探测纪律）
// 作剩余倒计时上限，不伪造字节进度；待服务端补 loaded_bytes 字段后，该卡
// 直接换用 estimateBytesEta 即可（接线点已留注释）。
