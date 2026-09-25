import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';

/// 星象台弹层（IA 裁决：监控降级为右上仪表胶囊+展开弹层，方案 §5.3）：
/// - KPI 行 4 卡 h96：KPI 28sp mono tabular（CountUp 仅首帧；实时 1s 直接换值
///   ——UX 评审 CountUp 限定场景）；迷你 sparkline；
/// - 主曲线卡：CPU/内存双系列（aurora/氢蓝 2dp），磁吸 crosshair（#9：吸附
///   <24dp spring 300/0.55 + 数值联动）、range 液态 Tab（#3）、图例点切
///   alpha 1→0.15（#22）；
/// - 任务吞吐柱状图：按日聚合（listTasks 真实数据，≤100 条封顶——如实标注），
///   range 切换柱高平滑长高（#23 spring 260/0.85，禁整排重画）；
/// - 告警条（内存阈值：warn 熔金 / crit nova，唯一信息性描边）+「星域平静」空态。
/// 数据源：/ws/monitor 实时窗口（壳层常驻单例）+ /monitor/history 回放 +
/// /tasks?status=running 计数；进程列表未做（服务端无进程 API，禁伪造）。
class MonitorSheet extends ConsumerStatefulWidget {
  const MonitorSheet({super.key});

  static Future<void> show(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return showDialog<void>(
      context: context,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      barrierLabel: '监控面板',
      builder: (_) => const Dialog(
        backgroundColor: Colors.transparent,
        child: MonitorSheet(),
      ),
    );
  }

  @override
  ConsumerState<MonitorSheet> createState() => _MonitorSheetState();
}

class _MonitorSheetState extends ConsumerState<MonitorSheet> {
  static const _ranges = <String>['实时', '1h', '6h', '24h'];
  static const _rangeKeys = <String?>[null, '1h', '6h', '24h'];

  String _rangeLabel = '实时';
  List<double> _historyCpu = [];
  List<double> _historyMem = [];
  bool _cpuVisible = true;
  bool _memVisible = true;
  int _runningCount = 0;
  double? _warnGb;
  double? _critGb;
  final ValueNotifier<FlSpot?> _hoverSpot = ValueNotifier(null);

  @override
  void initState() {
    super.initState();
    _loadThresholds();
    _refreshRunning();
    ref.listenManual(refreshEventsProvider, (_, _) => _refreshRunning());
  }

  @override
  void dispose() {
    _hoverSpot.dispose();
    super.dispose();
  }

  Future<void> _loadThresholds() async {
    try {
      final summary = await ref.read(apiClientProvider).configSummary();
      if (!mounted) return;
      final monitor = (summary['monitor'] as Map?)?.cast<String, dynamic>();
      setState(() {
        _warnGb = (monitor?['memory_warning_gb'] as num?)?.toDouble();
        _critGb = (monitor?['memory_critical_gb'] as num?)?.toDouble();
      });
    } on ApiError {
      // 阈值缺失 → 不画告警条（禁伪造阈值）
    }
  }

  Future<void> _refreshRunning() async {
    try {
      final items = await ref.read(apiClientProvider).listTasks(status: 'running');
      if (!mounted) return;
      setState(() => _runningCount = items.length);
    } on ApiError {
      // 计数失败保留旧值（瞬时档：stale-while-revalidate）
    }
  }

  /// range 切换：实时=WS 窗口；否则 REST 历史回放。
  Future<void> _switchRange(String label) async {
    setState(() => _rangeLabel = label);
    final key = _rangeKeys[_ranges.indexOf(label)];
    if (key == null) {
      setState(() {
        _historyCpu = [];
        _historyMem = [];
      });
      return;
    }
    try {
      final data = await ref.read(apiClientProvider).monitorHistory(key);
      if (!mounted) return;
      final points = (data['points'] as List?) ?? const [];
      final cpu = <double>[];
      final mem = <double>[];
      for (final raw in points) {
        final p = (raw as Map).cast<String, dynamic>();
        cpu.add((p['cpu_percent'] as num?)?.toDouble() ?? 0);
        mem.add((p['mem_percent'] as num?)?.toDouble() ?? 0);
      }
      setState(() {
        _historyCpu = cpu;
        _historyMem = mem;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final connection = ref.watch(connectionProvider);
    final windowNotifier = ref.watch(connectionProvider.notifier).monitorWindow;
    // WS 窗口经 ValueListenable 驱动重绘（1s 一个新实例，watch 语义干净）
    return ValueListenableBuilder<MonitorWindow>(
      valueListenable: windowNotifier,
      builder: (context, window, _) => _SheetBody(
        palette: palette,
        connection: connection.status,
        window: window,
        rangeLabel: _rangeLabel,
        historyCpu: _historyCpu,
        historyMem: _historyMem,
        cpuVisible: _cpuVisible,
        memVisible: _memVisible,
        runningCount: _runningCount,
        warnGb: _warnGb,
        critGb: _critGb,
        hoverSpot: _hoverSpot,
        onRangeSwitch: _switchRange,
        onLegendToggle: (series) {
          setState(() {
            if (series == 0) _cpuVisible = !_cpuVisible;
            if (series == 1) _memVisible = !_memVisible;
          });
        },
      ),
    );
  }
}

/// 弹层内容体（由 ValueListenableBuilder 重建，避免整 State 依赖窗口实例）。
class _SheetBody extends StatelessWidget {
  const _SheetBody({
    required this.palette,
    required this.connection,
    required this.window,
    required this.rangeLabel,
    required this.historyCpu,
    required this.historyMem,
    required this.cpuVisible,
    required this.memVisible,
    required this.runningCount,
    required this.warnGb,
    required this.critGb,
    required this.hoverSpot,
    required this.onRangeSwitch,
    required this.onLegendToggle,
  });

  final AstroPalette palette;
  final WsStatus connection;
  final MonitorWindow window;
  final String rangeLabel;
  final List<double> historyCpu;
  final List<double> historyMem;
  final bool cpuVisible;
  final bool memVisible;
  final int runningCount;
  final double? warnGb;
  final double? critGb;
  final ValueNotifier<FlSpot?> hoverSpot;
  final ValueChanged<String> onRangeSwitch;
  final ValueChanged<int> onLegendToggle;

  static const _ranges = <String>['实时', '1h', '6h', '24h'];

  _Severity _memSeverity(double? gb) {
    if (gb == null) return _Severity.none;
    if (critGb != null && gb > critGb!) return _Severity.crit;
    if (warnGb != null && gb > warnGb!) return _Severity.warn;
    return _Severity.none;
  }

  @override
  Widget build(BuildContext context) {
    final live = rangeLabel == '实时';
    final cpuSeries = live ? window.cpu : historyCpu;
    final memSeries = live ? window.mem : historyMem;

    return Container(
      constraints: const BoxConstraints(maxWidth: 720, maxHeight: 640),
      padding: const EdgeInsets.all(AstroSpace.card),
      decoration: BoxDecoration(
        color: palette.bg,
        borderRadius: BorderRadius.circular(AstroRadius.lg),
        border: Border.all(color: palette.stroke),
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ---- 头部：连接态 + range 液态 Tab ----
            Row(
              children: [
                Text('星象台',
                    style: TextStyle(
                        fontSize: AstroType.h2.size,
                        fontWeight: AstroType.h2.weight,
                        color: palette.ink900)),
                const SizedBox(width: 8),
                _ConnectionTag(connection: connection, palette: palette),
                const Spacer(),
                _RangeTabs(
                  labels: _ranges,
                  selected: rangeLabel,
                  palette: palette,
                  onSelect: onRangeSwitch,
                ),
              ],
            ),
            const SizedBox(height: AstroSpace.gapLg),

            // ---- KPI 行（4 卡 h96）----
            Row(
              children: [
                Expanded(
                  child: _KpiCard(
                    label: 'CPU',
                    value: window.latest?.cpuPercent,
                    unit: '%',
                    fractionMax: 100,
                    series: live ? window.cpu : const [],
                    palette: palette,
                    line: palette.aurora,
                  ),
                ),
                const SizedBox(width: AstroSpace.gap),
                Expanded(
                  child: _KpiCard(
                    label: '内存',
                    value: window.latest?.memUsedGb,
                    unit: 'GB',
                    fractionMax: critGb ?? 16,
                    series: live
                        ? window.mem
                            .map((p) => p / 100 * (critGb ?? 16))
                            .toList()
                        : const [],
                    palette: palette,
                    line: palette.hydrogen,
                    severity: _memSeverity(window.latest?.memUsedGb),
                  ),
                ),
                const SizedBox(width: AstroSpace.gap),
                Expanded(
                  child: _KpiCard(
                    label: '磁盘',
                    value: window.latest?.diskMbps,
                    unit: 'MB/s',
                    fractionMax: 200,
                    series: live ? window.disk : const [],
                    palette: palette,
                    line: palette.ink600,
                  ),
                ),
                const SizedBox(width: AstroSpace.gap),
                Expanded(
                  child: _KpiCard(
                    label: '运行任务',
                    value: runningCount.toDouble(),
                    unit: '',
                    fractionMax: 8,
                    series: const [],
                    palette: palette,
                    line: palette.aurora,
                    isCount: true,
                  ),
                ),
              ],
            ),

            // ---- 告警条 / 星域平静 ----
            const SizedBox(height: AstroSpace.gapLg),
            _AlertStrip(
              severity: _memSeverity(window.latest?.memUsedGb),
              runningCount: runningCount,
              palette: palette,
            ),

            // ---- 主曲线卡 ----
            const SizedBox(height: AstroSpace.gapLg),
            _CurveCard(
              palette: palette,
              cpu: cpuSeries,
              mem: memSeries,
              cpuVisible: cpuVisible,
              memVisible: memVisible,
              hoverSpot: hoverSpot,
              onLegendToggle: onLegendToggle,
            ),

            // ---- 任务吞吐柱状图（按日；≤100 条封顶如实标注）----
            const SizedBox(height: AstroSpace.gapLg),
            const _ThroughputBars(),
          ],
        ),
      ),
    );
  }
}

// ---- 连接态标签（胶囊兼常驻服务连接态）----

enum _Severity { none, warn, crit }

class _ConnectionTag extends StatelessWidget {
  const _ConnectionTag({required this.connection, required this.palette});

  final WsStatus connection;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final (text, color) = switch (connection) {
      WsStatus.connected => ('已连接', palette.auroraText),
      WsStatus.connecting => ('连接中', palette.moltenText),
      WsStatus.disconnected => ('未连接', palette.nova),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AstroRadius.pill),
      ),
      child: Text(
        '${AstroIcons.statusOk} $text',
        style: TextStyle(fontSize: AstroType.label.size, color: color),
      ),
    );
  }
}

// ---- range 液态 Tab（#3 spring 300/0.6）----

class _RangeTabs extends StatefulWidget {
  const _RangeTabs({
    required this.labels,
    required this.selected,
    required this.palette,
    required this.onSelect,
  });

  final List<String> labels;
  final String selected;
  final AstroPalette palette;
  final ValueChanged<String> onSelect;

  @override
  State<_RangeTabs> createState() => _RangeTabsState();
}

class _RangeTabsState extends State<_RangeTabs>
    with SingleTickerProviderStateMixin {
  late final AnimationController _slide = AnimationController(vsync: this);
  late int _selected = widget.labels.contains(widget.selected)
      ? widget.labels.indexOf(widget.selected)
      : 0;
  late int _from = _selected;
  late int _to = _selected;

  @override
  void didUpdateWidget(_RangeTabs oldWidget) {
    super.didUpdateWidget(oldWidget);
    final next = widget.labels.indexOf(widget.selected);
    if (next != _to) {
      _from = _to;
      _to = next;
      _selected = next;
      // spring(300, 0.6)（§1.4 #3；ζ0.6 → damping=0.6*2*sqrt(300)）
      const stiffness = 300.0;
      final damping = 0.6 * 2 * math.sqrt(stiffness);
      _slide.animateWith(
        SpringSimulation(
          SpringDescription(mass: 1, stiffness: stiffness, damping: damping),
          0,
          1,
          0,
        ),
      );
    }
  }

  @override
  void dispose() {
    _slide.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    return Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: palette.container,
        borderRadius: BorderRadius.circular(AstroRadius.pill),
      ),
      child: AnimatedBuilder(
        animation: _slide,
        builder: (context, _) {
          final t = _slide.value;
          return Stack(
            alignment: Alignment.centerLeft,
            children: [
              // 液态指示胶囊（拉长→收缩由 spring 物理给出）
              FractionallySizedBox(
                widthFactor: 1 / widget.labels.length,
                child: FractionalTranslation(
                  translation: Offset(_lerp(_from, _to, t), 0),
                  child: Container(
                    height: 26,
                    decoration: BoxDecoration(
                      color: palette.card,
                      borderRadius:
                          BorderRadius.circular(AstroRadius.pill),
                    ),
                  ),
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (var i = 0; i < widget.labels.length; i++)
                    InkWell(
                      onTap: () => widget.onSelect(widget.labels[i]),
                      child: Container(
                        width: 52,
                        height: 26,
                        alignment: Alignment.center,
                        child: Text(
                          widget.labels[i],
                          style: TextStyle(
                            fontSize: AstroType.label.size,
                            fontWeight: i == _selected
                                ? FontWeight.w600
                                : FontWeight.w400,
                            color: i == _selected
                                ? palette.ink900
                                : palette.ink600,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }

  double _lerp(int a, int b, double t) => a + (b - a) * t;
}

// ---- KPI 卡（h96；CountUp 仅首帧，实时直接换值）----

class _KpiCard extends StatefulWidget {
  const _KpiCard({
    required this.label,
    required this.value,
    required this.unit,
    required this.fractionMax,
    required this.series,
    required this.palette,
    required this.line,
    this.severity = _Severity.none,
    this.isCount = false,
  });

  final String label;
  final double? value;
  final String unit;
  final double fractionMax;
  final List<double> series;
  final AstroPalette palette;
  final Color line;
  final _Severity severity;
  final bool isCount;

  @override
  State<_KpiCard> createState() => _KpiCardState();
}

class _KpiCardState extends State<_KpiCard> {
  bool _firstFrameDone = false;

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    final value = widget.value;
    final severityColor = switch (widget.severity) {
      _Severity.none => null,
      _Severity.warn => palette.molten,
      _Severity.crit => palette.nova,
    };
    return AnimatedContainer(
      duration: const Duration(milliseconds: AstroMotion.tweenColorMs),
      height: 96,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: palette.card,
        borderRadius: BorderRadius.circular(AstroRadius.md),
        // 唯一信息性描边：内存告警 molten/nova（星空设计系统规格 §二）
        border: severityColor != null
            ? Border.all(color: severityColor, width: 1.5)
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.label,
              style: TextStyle(
                  fontSize: AstroType.label.size, color: palette.ink400)),
          const Spacer(),
          _KpiValue(
            value: value,
            isCount: widget.isCount,
            color: severityColor ?? palette.ink900,
            firstFrameDone: _firstFrameDone,
            onFirstFrameDone: () {
              if (mounted) setState(() => _firstFrameDone = true);
            },
          ),
          Text(widget.unit,
              style: TextStyle(
                  fontSize: AstroType.caption.size, color: palette.ink400)),
          if (widget.series.isNotEmpty)
            SizedBox(
              height: 16,
              width: double.infinity,
              child: CustomPaint(
                painter: _Sparkline(
                  series: widget.series,
                  max: widget.fractionMax,
                  color: widget.line,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// 迷你 sparkline：线 1.5dp + 面 8%（规格 §三.6）。
class _Sparkline extends CustomPainter {
  const _Sparkline({required this.series, required this.max, required this.color});

  final List<double> series;
  final double max;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (series.isEmpty) return;
    final stepX = size.width / (series.length - 1).clamp(1, 1 << 30);
    final path = Path();
    for (var i = 0; i < series.length; i++) {
      final x = i * stepX;
      final y = size.height -
          (series[i].clamp(0, max) / max) * size.height;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    // 面 8%
    final fill = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(fill, Paint()..color = color.withValues(alpha: 0.08));
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
  }

  @override
  bool shouldRepaint(_Sparkline oldDelegate) =>
      oldDelegate.series != series || oldDelegate.color != color;
}

// ---- 告警条 / 星域平静空态（监控页永远不空屏）----

class _AlertStrip extends StatelessWidget {
  const _AlertStrip({
    required this.severity,
    required this.runningCount,
    required this.palette,
  });

  final _Severity severity;
  final int runningCount;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final calm = severity == _Severity.none && runningCount == 0;
    final color = switch (severity) {
      _Severity.none => palette.auroraText,
      _Severity.warn => palette.moltenText,
      _Severity.crit => palette.nova,
    };
    final text = switch (severity) {
      _Severity.none => runningCount == 0 ? '一切平静 · 无运行任务 · 无告警' : '运行任务 $runningCount · 无告警',
      _Severity.warn => '内存超预警阈值 ▲ 建议收任务',
      _Severity.crit => '内存超红线 ✕ 请立即收任务',
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: severity == _Severity.none
            ? palette.card
            : palette.alertWashBg,
        borderRadius: BorderRadius.circular(AstroRadius.sm),
        border: severity == _Severity.warn
            ? Border.all(color: palette.molten, width: 1.5)
            : severity == _Severity.crit
                ? Border.all(color: palette.nova, width: 1.5)
                : null,
      ),
      child: Text(
        calm ? '${AstroIcons.navHome} $text（星域平静）' : '${AstroIcons.statusWarn} $text',
        style: TextStyle(fontSize: AstroType.bodySm.size, color: color),
      ),
    );
  }
}

// ---- 主曲线卡（磁吸 crosshair + 图例点切）----

class _CurveCard extends StatelessWidget {
  const _CurveCard({
    required this.palette,
    required this.cpu,
    required this.mem,
    required this.cpuVisible,
    required this.memVisible,
    required this.hoverSpot,
    required this.onLegendToggle,
  });

  final AstroPalette palette;
  final List<double> cpu;
  final List<double> mem;
  final bool cpuVisible;
  final bool memVisible;
  final ValueNotifier<FlSpot?> hoverSpot;
  final ValueChanged<int> onLegendToggle;

  List<FlSpot> spotsOf(List<double> series) => [
        for (var i = 0; i < series.length; i++) FlSpot(i.toDouble(), series[i]),
      ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AstroSpace.card),
      decoration: BoxDecoration(
        color: palette.card,
        borderRadius: BorderRadius.circular(AstroRadius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _LegendChip(
                label: 'CPU',
                color: palette.aurora,
                visible: cpuVisible,
                palette: palette,
                onTap: () => onLegendToggle(0),
              ),
              const SizedBox(width: 12),
              _LegendChip(
                label: '内存',
                color: palette.hydrogen,
                visible: memVisible,
                palette: palette,
                onTap: () => onLegendToggle(1),
              ),
              const Spacer(),
              ValueListenableBuilder<FlSpot?>(
                valueListenable: hoverSpot,
                builder: (context, spot, _) {
                  // 磁吸码表：吸附点数值 mono tabular
                  final text = spot == null
                      ? '悬停查看 · 吸附最近点'
                      : 't${spot.x.toInt()} · CPU ${spot.y.toStringAsFixed(1)}%';
                  return Text(
                    text,
                    style: TextStyle(
                      fontFamily: AstroType.monoFamily,
                      fontSize: AstroType.caption.size,
                      color: spot == null ? palette.ink400 : palette.auroraText,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: AstroSpace.gap),
          SizedBox(
            height: 180,
            child: cpu.isEmpty && mem.isEmpty
                ? Center(
                    child: Text(
                      _rangeHintText,
                      style: TextStyle(
                          fontSize: AstroType.bodySm.size,
                          color: palette.ink400),
                    ),
                  )
                : LineChart(
                    LineChartData(
                      minY: 0,
                      maxY: 100,
                      gridData: const FlGridData(show: false),
                      titlesData: const FlTitlesData(show: false),
                      borderData: FlBorderData(show: false),
                      // 磁吸 crosshair（#9）：吸附阈值 24dp
                      lineTouchData: LineTouchData(
                        enabled: true,
                        handleBuiltInTouches: true,
                        touchSpotThreshold: 24,
                        touchCallback: (event, response) {
                          final spot =
                              response?.lineBarSpots?.firstOrNull;
                          hoverSpot.value = spot == null
                              ? null
                              : FlSpot(spot.x, spot.y);
                        },
                        getTouchedSpotIndicator: (barData, indicators) =>
                            indicators
                                .map(
                                  (_) => TouchedSpotIndicatorData(
                                    // 磁吸游标竖线（吸附后 1dp 描边色）
                                    FlLine(
                                        color: palette.stroke, strokeWidth: 1),
                                    FlDotData(
                                      show: true,
                                      getDotPainter: (spot, _, _, _) =>
                                          FlDotCirclePainter(
                                        radius: 4,
                                        color: palette.aurora,
                                        strokeColor: palette.card,
                                      ),
                                    ),
                                  ),
                                )
                                .toList(),
                      ),
                      lineBarsData: [
                        if (cpuVisible)
                          LineChartBarData(
                            spots: spotsOf(cpu),
                            isCurved: true,
                            color: palette.aurora,
                            barWidth: 2,
                            dotData: const FlDotData(show: false),
                          ),
                        if (memVisible)
                          LineChartBarData(
                            spots: spotsOf(mem),
                            isCurved: true,
                            color: palette.hydrogen,
                            barWidth: 2,
                            dotData: const FlDotData(show: false),
                          ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  String get _rangeHintText => '等待 /ws/monitor 实时采样（约 1s 一个点）';
}

/// 图例点切（#22：alpha 1→0.15，TWEEN_COLOR 150ms）。
class _LegendChip extends StatelessWidget {
  const _LegendChip({
    required this.label,
    required this.color,
    required this.visible,
    required this.palette,
    required this.onTap,
  });

  final String label;
  final Color color;
  final bool visible;
  final AstroPalette palette;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AstroRadius.pill),
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: AstroMotion.tweenColorMs),
        opacity: visible ? 1 : 0.15,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration:
                  BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                    fontSize: AstroType.caption.size, color: palette.ink600)),
          ],
        ),
      ),
    );
  }
}

// ---- 任务吞吐柱状图（#23 柱高平滑长高）----

class _ThroughputBars extends ConsumerStatefulWidget {
  const _ThroughputBars();

  @override
  ConsumerState<_ThroughputBars> createState() => _ThroughputBarsState();
}

class _ThroughputBarsState extends ConsumerState<_ThroughputBars> {
  List<int> _counts = [];
  List<String> _days = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await ref.read(apiClientProvider).listTasks();
      if (!mounted) return;
      // 按日聚合（真实 listTasks 数据；分页上限 100 条——如实标注不伪造）
      final buckets = <String, int>{};
      final days = <String>[];
      for (var i = 6; i >= 0; i--) {
        final day = DateTime.now().subtract(Duration(days: i));
        final key =
            '${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
        buckets[key] = 0;
        days.add(key);
      }
      for (final raw in items) {
        final t = (raw as Map)['created_at'] as String?;
        final time = DateTime.tryParse(t ?? '');
        if (time == null) continue;
        final key =
            '${time.year}-${time.month.toString().padLeft(2, '0')}-${time.day.toString().padLeft(2, '0')}';
        if (buckets.containsKey(key)) buckets[key] = buckets[key]! + 1;
      }
      setState(() {
        _counts = [for (final d in days) buckets[d]!];
        _days = days;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = '[${e.code}] ${e.message}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Container(
      padding: const EdgeInsets.all(AstroSpace.card),
      decoration: BoxDecoration(
        color: palette.card,
        borderRadius: BorderRadius.circular(AstroRadius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('任务吞吐 · 按日',
                  style: TextStyle(
                      fontSize: AstroType.titleSm.size,
                      fontWeight: FontWeight.w500,
                      color: palette.ink900)),
              const Spacer(),
              Text('近 7 日（基于最近 100 条任务）',
                  style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink400)),
              TextButton(
                onPressed: _load,
                child: Text('刷新',
                    style: TextStyle(
                        fontSize: AstroType.caption.size,
                        color: palette.ink400)),
              ),
            ],
          ),
          const SizedBox(height: AstroSpace.gap),
          if (_error != null)
            Text('加载失败：$_error',
                style: TextStyle(
                    fontSize: AstroType.bodySm.size, color: palette.nova))
          else if (_counts.isEmpty)
            Text('暂无数据',
                style: TextStyle(
                    fontSize: AstroType.bodySm.size, color: palette.ink400))
          else
            SizedBox(
              height: 96,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  for (var i = 0; i < _counts.length; i++)
                    Expanded(
                      child: _SpringBar(
                        // range 切换/数据到达：柱高原值→新值平滑（#23 SPRING_SOFT）
                        fraction: _maxCount == 0
                            ? 0.0
                            : _counts[i] / _maxCount,
                        palette: palette,
                      ),
                    ),
                ],
              ),
            ),
          const SizedBox(height: 4),
          Row(
            children: [
              for (final day in _days)
                Expanded(
                  child: Text(
                    day.substring(5),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: AstroType.label.size,
                        color: palette.ink400,
                        fontFeatures: const [FontFeature.tabularFigures()]),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  int get _maxCount => _counts.fold(1, (a, b) => b > a ? b : a);
}

/// 单柱：SPRING_SOFT(260/0.85) 驱动高度过渡（禁整排重画——每柱独立动画）。
class _SpringBar extends StatefulWidget {
  const _SpringBar({required this.fraction, required this.palette});

  final double fraction;
  final AstroPalette palette;

  @override
  State<_SpringBar> createState() => _SpringBarState();
}

class _SpringBarState extends State<_SpringBar>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this);
  late double _from = 0;
  late double _to = widget.fraction;

  @override
  void initState() {
    super.initState();
    _animate();
  }

  @override
  void didUpdateWidget(_SpringBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.fraction != widget.fraction) {
      _from = _to;
      _to = widget.fraction;
      _animate();
    }
  }

  void _animate() {
    final stiffness = AstroMotion.springSoft.stiffness;
    final damping =
        AstroMotion.springSoft.damping * 2 * math.sqrt(stiffness);
    _controller.animateWith(SpringSimulation(
      SpringDescription(mass: 1, stiffness: stiffness, damping: damping),
      0,
      1,
      0,
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 3),
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          final value = _from + (_to - _from) * _controller.value;
          return LayoutBuilder(
            builder: (context, constraints) => Align(
              alignment: Alignment.bottomCenter,
              child: Container(
                height: (constraints.maxHeight * value).clamp(2.0, double.infinity),
                width: 18,
                decoration: BoxDecoration(
                  color: value > 0 ? palette.aurora : palette.container,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}



/// KPI 数值：CountUp 400ms 仅首帧到达（UX 评审限定场景）；实时 1s 直接换值
/// （tabular 等宽防跳宽，禁逐次滚动）。
class _KpiValue extends StatelessWidget {
  const _KpiValue({
    required this.value,
    required this.isCount,
    required this.color,
    required this.firstFrameDone,
    required this.onFirstFrameDone,
  });

  final double? value;
  final bool isCount;
  final Color color;
  final bool firstFrameDone;
  final VoidCallback onFirstFrameDone;

  String _format(double v) => isCount
      ? '${v.toInt()}'
      : v >= 100
          ? v.toStringAsFixed(0)
          : v.toStringAsFixed(1);

  TextStyle _style() => TextStyle(
        fontFamily: AstroType.monoFamily,
        fontSize: AstroType.kpi.size,
        height: AstroType.kpi.height / AstroType.kpi.size,
        fontWeight: AstroType.kpi.weight,
        color: color,
        fontFeatures: const [FontFeature.tabularFigures()],
      );

  @override
  Widget build(BuildContext context) {
    final value = this.value;
    if (value == null) {
      return Text('--', style: _style());
    }
    if (!firstFrameDone) {
      // 首帧：0→N CountUp（400ms，tween 曲线库）
      return TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value),
        duration: const Duration(milliseconds: 400),
        curve: AstroMotion.tweenEasing,
        onEnd: onFirstFrameDone,
        builder: (context, v, _) => Text(_format(v), style: _style()),
      );
    }
    return Text(_format(value), style: _style());
  }
}
