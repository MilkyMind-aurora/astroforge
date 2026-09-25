import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/ws_client/ws_client.dart';
import 'monitor_sheet.dart';

/// 右上仪表胶囊（IA 裁决：监控降级为右上胶囊+展开弹层；UX P1 常驻连接位）：
/// - 常驻承载服务连接态（●已连接 aurora / ◌重连中 nova 闪 / 连接中 熔金）；
/// - 附 CPU% 与内存 GB mono 实时值（/ws/monitor 壳层常驻单例）；
/// - 点击展开星象台弹层（MonitorSheet）。
class GaugeCapsule extends ConsumerWidget {
  const GaugeCapsule({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final palette = AstroPaletteScope.of(context);
    final connection = ref.watch(connectionProvider);
    final sample =
        ref.watch(connectionProvider.notifier).monitorWindow.value.latest;

    final (dotColor, label) = switch (connection.status) {
      WsStatus.connected => (palette.aurora, '已连接'),
      WsStatus.connecting => (palette.molten, '连接中'),
      WsStatus.disconnected => (palette.nova, '重连中'),
    };
    return Tooltip(
      message: '服务连接态与实时仪表（点击展开星象台）',
      child: InkWell(
        onTap: () => MonitorSheet.show(context),
        borderRadius: BorderRadius.circular(AstroRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: palette.card.withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(AstroRadius.pill),
            border: Border.all(color: palette.stroke),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              // 连接态点（断连 nova；重连呼吸由弹层与横幅承担，胶囊保持克制）
              _ConnectionDot(color: dotColor, breathing: connection.status == WsStatus.disconnected),
              const SizedBox(width: 6),
              Text(label,
                  style: TextStyle(
                      fontSize: AstroType.label.size, color: palette.ink600)),
              if (sample != null) ...[
                const SizedBox(width: 10),
                Text(
                  'CPU ${sample.cpuPercent.toStringAsFixed(0)}%',
                  style: TextStyle(
                    fontFamily: AstroType.monoFamily,
                    fontSize: AstroType.caption.size,
                    color: palette.ink600,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${sample.memUsedGb.toStringAsFixed(1)}GB',
                  style: TextStyle(
                    fontFamily: AstroType.monoFamily,
                    fontSize: AstroType.caption.size,
                    // 内存阈值变色（>warn 熔金 / >crit nova）由弹层告警条细化，
                    // 胶囊保持单色（层级靠明度）
                    color: palette.ink900,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
              const SizedBox(width: 6),
              Text(AstroIcons.miscCaretDown,
                  style: TextStyle(fontSize: 10, color: palette.ink400)),
            ],
          ),
        ),
      ),
    );
  }
}

/// 连接态点：断连时 nova 呼吸（1.2s 循环，dur-loop 档）。
class _ConnectionDot extends StatefulWidget {
  const _ConnectionDot({required this.color, required this.breathing});

  final Color color;
  final bool breathing;

  @override
  State<_ConnectionDot> createState() => _ConnectionDotState();
}

class _ConnectionDotState extends State<_ConnectionDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (widget.breathing && !MediaQuery.disableAnimationsOf(context)) {
      _breath.repeat(reverse: true);
    } else {
      _breath.stop();
    }
  }

  @override
  void didUpdateWidget(_ConnectionDot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.breathing != oldWidget.breathing) {
      if (widget.breathing && !MediaQuery.disableAnimationsOf(context)) {
        _breath.repeat(reverse: true);
      } else {
        _breath.stop();
      }
    }
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _breath,
      builder: (context, _) {
        final alpha =
            widget.breathing ? 0.35 + 0.65 * _breath.value : 1.0;
        return Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(
            color: widget.color.withValues(alpha: alpha),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }
}
