import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:yaml/yaml.dart';

import '../design/design.dart';
export 'starling_engine.dart';
import 'starling_engine.dart';
import 'starling_painter.dart';

/// 星仔渲染位（单一活跃原则由宿主保证：同屏最多 1 个动效位——星仔规格 §三）。
/// 本体不漂浮；生命感 = 6~14s 眨眼 + 视线缓漂（V2-2 bloub 实证纪律）。
/// reduced-motion：每状态单帧（frozenAt t=0），眨眼保留固定 10s 间隔淡切。
class StarlingView extends StatefulWidget {
  const StarlingView({
    required this.size,
    this.state = StarlingState.idle,
    this.primitive = StarlingPrimitive.none,
    super.key,
  });

  final double size;
  final StarlingState state;
  final StarlingPrimitive primitive;

  @override
  State<StarlingView> createState() => _StarlingViewState();
}

class _StarlingViewState extends State<StarlingView>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  double _seconds = 0;
  final BlinkScheduler _blink = BlinkScheduler();
  bool _reduced = false;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_onTick)..start();
  }

  void _onTick(Duration elapsed) {
    if (!mounted) return;
    if (_reduced) return; // 单帧静置（金测/降级）
    setState(() => _seconds = elapsed.inMicroseconds / 1e6);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final t = _reduced ? 0.0 : _seconds;
    final blinkT = _reduced
        ? (t % 10 < 0.12 ? (t % 10) / 0.12 : 0.0) // reduced：固定 10s 间隔
        : _blink.tick(t);
    // 视线缓漂（20~40s 扫视的连续近似；限幅 ±2dp 由引擎保证）
    final gaze = Offset(
      2 * math.sin(t * 2 * math.pi / 24),
      1.2 * math.sin(t * 2 * math.pi / 31),
    );
    final pose = sampleStarling(
      state: widget.state,
      t: t,
      primitive: widget.primitive,
      blinkT: blinkT,
      gaze: gaze,
    );
    return SizedBox.square(
      dimension: widget.size,
      child: CustomPaint(
        painter: StarlingPainter(
          pose: pose,
          palette: palette,
          backgroundColor: palette.bg,
        ),
      ),
    );
  }
}

/// 台词库读取（config/design/quotes.yaml 镜像资产；L1 数据插件——禁硬编码文案）。
class StarlingQuotes {
  StarlingQuotes._(Map<String, List<String>> events) : _events = events;

  final Map<String, List<String>> _events;
  static StarlingQuotes? _cache;

  static Future<StarlingQuotes> load() async {
    final cached = _cache;
    if (cached != null) return cached;
    final raw = await rootBundle.loadString('assets/design/quotes.yaml');
    final doc = loadYaml(raw) as YamlMap;
    final events = <String, List<String>>{};
    for (final entry in ((doc['events'] ?? YamlMap()) as YamlMap).entries) {
      final lines = (entry.value as YamlMap)['lines'] as YamlList?;
      if (lines != null) {
        events[entry.key as String] =
            lines.map((l) => l.toString()).toList(growable: false);
      }
    }
    final quotes = StarlingQuotes._(events);
    _cache = quotes;
    return quotes;
  }

  /// 今日星语：日期种子伪随机、当日固定（星仔规格 §三 轨底头像触发位）。
  String quoteOfDay(DateTime now) {
    final pool = _events['boot'] ?? const [];
    if (pool.isEmpty) return '';
    final seed = now.year * 10000 + now.month * 100 + now.day;
    return pool[math.Random(seed).nextInt(pool.length)];
  }

  String byEvent(String event, [math.Random? random]) {
    final pool = _events[event] ?? const [];
    if (pool.isEmpty) return '';
    return pool[(random ?? math.Random()).nextInt(pool.length)];
  }
}
