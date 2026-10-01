import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 任务完成极光横幅（§1.8 #18，渐变白名单位①）：galaxy 三停驻渐变横幅 +
/// 高光 900ms 扫过（规格 #18 时长），任务完成瞬间的 hero 触达位。
/// 白名单纪律：AstroGalaxy 消费处 ①本横幅 ②AI 抽屉头饰线 ③TUI 启动横幅，
/// 同屏 ≤1——本横幅为瞬时（~3s 自动退场），常态不与 ② 同屏占位。
/// reduced-motion：静态横幅（无扫过），仍可自动退场。
class AuroraBanner extends StatefulWidget {
  const AuroraBanner({
    required this.message,
    this.onDismissed,
    this.visibleDurationMs = 3000,
    super.key,
  });

  final String message;
  final VoidCallback? onDismissed;

  /// 横幅停留时长（自动退场；瞬时反馈红线只约束交互反馈，庆祝位按规格留场）。
  final int visibleDurationMs;

  @override
  State<AuroraBanner> createState() => _AuroraBannerState();
}

class _AuroraBannerState extends State<AuroraBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _sweep = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900), // 高光扫过 900ms（规格 #18）
  );

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(
      Duration(milliseconds: widget.visibleDurationMs),
      () {
        if (mounted) widget.onDismissed?.call();
      },
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!MediaQuery.disableAnimationsOf(context) && !_sweep.isAnimating) {
      _sweep.forward();
    } else if (MediaQuery.disableAnimationsOf(context)) {
      _sweep.value = 0; // reduced-motion：无扫过（静态渐变横幅）
    }
  }

  @override
  void dispose() {
    _sweep.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // 视觉审计 high 项：昼档 galaxy 亮底无合法字色（WCAG 实测：昼字 #F6F7FC
    // on 昼停驻 #0C9B7E 仅 3.27:1 <4.5；深字 on 昼停驻 5.75/4.14/3.51 仍两档
    // 不过）——两主题统一「夜档亮停驻 + 固定深字」，最劣停驻 6.05:1 全过
    // （12.21/6.05/10.04，13sp w500 AA 4.5 线）。昼停驻取值回写 tokens.yaml
    // 白名单位与规格 §四 属工具链/设计源改动，已登记 visual-review backlog。
    final ink = AstroPalette.dark.bg; // 固定深字（tokens 取值，禁散落色值）
    return ClipRRect(
      borderRadius: BorderRadius.circular(AstroRadius.md),
      child: Stack(
        children: [
          // 银河渐变底（三停驻，横向贯穿；两主题统一夜档亮停驻）
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                  stops: AstroGalaxy.positions,
                  colors: AstroGalaxy.darkStops,
                ),
              ),
            ),
          ),
          // 高光扫过：窄亮带自左向右平移 900ms 一次
          AnimatedBuilder(
            animation: _sweep,
            builder: (context, _) {
              if (_sweep.value == 0) return const SizedBox.shrink();
              return LayoutBuilder(
                builder: (context, constraints) {
                  final w = constraints.maxWidth;
                  final x = -w * 0.35 +
                      (w * 1.7) * Curves.easeInOut.transform(_sweep.value);
                  return Transform.translate(
                    offset: Offset(x, 0),
                    child: Container(
                      width: w * 0.35,
                      // 高光带白 18% → 0 横向衰减
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Colors.white.withValues(alpha: 0.0),
                            Colors.white.withValues(alpha: 0.18),
                            Colors.white.withValues(alpha: 0.0),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              );
            },
          ),
          // 内容：状态星符 + 文案（固定深字 on 亮停驻——WCAG 12.21/6.05/10.04
          // 双主题全过，见 build 头注释；字色不再随 palette 翻转）
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
            child: Row(
              children: [
                Text(
                  AstroIcons.taskSuccess,
                  style: TextStyle(
                    fontSize: AstroType.body.size,
                    color: ink,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    widget.message,
                    style: TextStyle(
                      fontSize: AstroType.bodySm.size,
                      fontWeight: FontWeight.w500,
                      color: ink,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
