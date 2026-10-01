import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:yaml/yaml.dart';

import '../design/design.dart';
export 'starling_engine.dart';
import 'starling_engine.dart';
import 'starling_painter.dart';

/// 星仔渲染位（单一活跃原则由 StarlingDirector 宿主仲裁（_StarlingDirector 单例）：同屏最多 1 个动效位
/// ——星仔规格 §三；不可见/失焦实例停表静帧）。本体不漂浮；生命感 =
/// 6~14s 眨眼 + 视线缓漂（V2-2 bloub 实证纪律）。
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
  bool _registered = false;

  @override
  void initState() {
    super.initState();
    // 表常建但不起跑：起跑权在 StarlingDirector（非活跃位零帧成本）
    _ticker = createTicker(_onTick);
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
    if (!_registered) {
      _registered = true;
      _starlingDirector.register(this);
    } else {
      _starlingDirector.refresh(this);
    }
  }

  @override
  void dispose() {
    if (_registered) {
      _starlingDirector.unregister(this);
    }
    _ticker.dispose();
    super.dispose();
  }

  /// 由 StarlingDirector 调度：仅「唯一活跃位 + 前台 + 非 reduced」起跑。
  void _applyActivation(bool animate) {
    if (!mounted) return;
    final shouldRun = animate && !_reduced;
    if (shouldRun) {
      if (!(_ticker.isActive)) _ticker.start();
    } else if (_ticker.isActive) {
      _ticker.stop(); // 静帧：非活跃位冻结在当前帧（禁空转 60fps）
    }
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

/// 星仔单一活跃仲裁器（星仔规格 §三：同屏最多 1 个动效位，帧轮换仅可见位运行；
/// 视觉审计 medium 项落地——此前注释声称「宿主保证」但无宿主，各实例满帧重绘）。
/// 规则：最早注册且仍挂载的实例持唯一动效位；其余静帧；App 失焦（paused/
/// inactive/hidden）全停，回前台恢复——对齐星野失焦暂停纪律
/// （starfield_view.dart didChangeAppLifecycleState 同款）。
class _StarlingDirector with WidgetsBindingObserver {
  _StarlingDirector() {
    WidgetsBinding.instance.addObserver(this);
  }

  final List<_StarlingViewState> _views = <_StarlingViewState>[];
  bool _foreground = true;
  _StarlingViewState? _active;

  void register(_StarlingViewState view) {
    _views.add(view);
    _active ??= view;
    view._applyActivation(_isAnimating(view));
  }

  void unregister(_StarlingViewState view) {
    final wasActive = identical(_active, view);
    _views.remove(view);
    if (wasActive) {
      // 位让渡给最早注册的存活实例（如首页关闭后轨底头像接管）
      _active = _views.isNotEmpty ? _views.first : null;
      _active?._applyActivation(_isAnimating(_active));
    }
  }

  /// reduced-motion 等依赖变化后重估（不改持有权，只重算起停）。
  void refresh(_StarlingViewState view) {
    view._applyActivation(_isAnimating(view));
  }

  bool _isAnimating(_StarlingViewState? view) =>
      _foreground && identical(view, _active);

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    _active?._applyActivation(_foreground);
  }
}

final _StarlingDirector _starlingDirector = _StarlingDirector();

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
