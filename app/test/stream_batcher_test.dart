// AI 流式合批缓冲测试（§1.8 #5：帧节流增量 append，禁逐 delta/整列重排）。
import 'package:astroforge/data/ai/stream_batcher.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('StreamBatcher（T_STREAM 2~4 token/帧合批）', () {
    test('多段 delta 入缓冲后单帧只出一批（≥4 字起步）', () {
      final batcher = StreamBatcher();
      batcher.add('你');
      batcher.add('好');
      batcher.add('，');
      batcher.add('星');
      batcher.add('伴');
      final first = batcher.drain();
      expect(first.length, 4); // 最小批 4
      expect(batcher.hasPending, isTrue);
    });

    test('积压大时按 1/8 加速排空，多次 drain 后清零', () {
      final batcher = StreamBatcher();
      batcher.add('字' * 800);
      var drained = 0;
      while (batcher.hasPending) {
        drained += batcher.drain().length;
      }
      expect(drained, 800);
    });

    test('空缓冲 drain 返回空串', () {
      final batcher = StreamBatcher();
      expect(batcher.drain(), '');
    });

    test('flushAll 一次排空（ai_done 兜底）', () {
      final batcher = StreamBatcher();
      batcher.add('最终回复全文');
      expect(batcher.flushAll(), '最终回复全文');
      expect(batcher.hasPending, isFalse);
    });
  });
}
