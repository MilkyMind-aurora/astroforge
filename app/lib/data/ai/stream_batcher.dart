import 'dart:math' as math;

/// AI 流式合批缓冲（§1.8 #5 T_STREAM：2~4 token/帧合批，增量 append，
/// 禁逐 delta/整列重排）。纯数据结构，可单测：add 入缓冲、drain 按帧节流
/// 取批（≥minBatch 起步、积压大时按 1/backlogDivisor 加速排空）。
class StreamBatcher {
  final StringBuffer _buffer = StringBuffer();

  void add(String chunk) {
    if (chunk.isEmpty) return;
    _buffer.write(chunk);
  }

  bool get hasPending => _buffer.isNotEmpty;

  int get pendingLength => _buffer.length;

  /// 取一批（不超余量）；空缓冲返回空串。
  String drain({int minBatch = 4, int backlogDivisor = 8}) {
    final pending = _buffer.toString();
    if (pending.isEmpty) return '';
    final take = math.min(pending.length, math.max(minBatch, pending.length ~/ backlogDivisor));
    final chunk = pending.substring(0, take);
    _buffer
      ..clear()
      ..write(pending.substring(take));
    return chunk;
  }

  /// 清空并返回全部剩余（ai_done 兜底：以服务端全量为准前的排空）。
  String flushAll() {
    final all = _buffer.toString();
    _buffer.clear();
    return all;
  }
}
