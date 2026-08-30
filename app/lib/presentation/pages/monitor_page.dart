import 'dart:async';
import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../widgets/placeholder_page.dart';

/// 监控看板（Phase 1.2）：实时 CPU/内存曲线。
/// 当前用本地演示数据流验证 fl_chart 骨架；接入 /ws/monitor 属 Phase 9.5.1。
class MonitorPage extends StatefulWidget {
  const MonitorPage({super.key});

  @override
  State<MonitorPage> createState() => _MonitorPageState();
}

class _MonitorPageState extends State<MonitorPage> {
  final List<FlSpot> _cpuSpots = [];
  final List<FlSpot> _memSpots = [];
  Timer? _timer;
  final _random = Random();
  double _t = 0;

  @override
  void initState() {
    super.initState();
    // 演示数据流：1s 一个点，60 点窗口（真实数据源为 WS monitor 通道）
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() {
        _cpuSpots.add(FlSpot(_t, 20 + _random.nextDouble() * 30));
        _memSpots.add(FlSpot(_t, 45 + _random.nextDouble() * 15));
        _t++;
        if (_cpuSpots.length > 60) _cpuSpots.removeAt(0);
        if (_memSpots.length > 60) _memSpots.removeAt(0);
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Widget _chart(List<FlSpot> spots, Color color, String label) {
    return SizedBox(
      height: 180,
      child: LineChart(
        LineChartData(
          minY: 0,
          maxY: 100,
          lineTouchData: const LineTouchData(enabled: false),
          titlesData: const FlTitlesData(show: false),
          gridData: const FlGridData(show: false),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              color: color,
              barWidth: 2,
              dotData: const FlDotData(show: false),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PlaceholderPage(
      title: '监控看板',
      phase: 'Phase 1.2 · 9.5',
      description: 'NovaFlow 监控：曲线为本地演示流（骨架验证），实时数据源 /ws/monitor 与历史回放随后接入。',
      child: Column(
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('CPU %（演示流）'),
                  _chart(_cpuSpots, const Color(0xFF4FC3F7), 'CPU'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('内存 %（演示流）'),
                  _chart(_memSpots, const Color(0xFF8B7CF6), 'MEM'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
