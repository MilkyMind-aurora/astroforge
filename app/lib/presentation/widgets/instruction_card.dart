import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 生长式弹出包装（#12：scale 0.85→1.02→1，pivot=触发位；SPRING_POP 320/0.72）。
/// 指令卡/任务确认卡共用（§5.2 与首页输入条共用指令卡组件）。
class GrowIn extends StatefulWidget {
  const GrowIn({required this.child, this.alignment = Alignment.topCenter, super.key});

  final Widget child;
  final Alignment alignment;

  @override
  State<GrowIn> createState() => _GrowInState();
}

class _GrowInState extends State<GrowIn> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  bool _reduced = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    );
    _scale = TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween(begin: 0.85, end: 1.02)
            .chain(CurveTween(curve: Curves.easeOutCubic)),
        weight: 70,
      ),
      TweenSequenceItem(
        tween: Tween(begin: 1.02, end: 1.0)
            .chain(CurveTween(curve: Curves.easeOutCubic)),
        weight: 30,
      ),
    ]).animate(_controller);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
    if (_reduced) {
      _controller.value = 1.0;
    } else if (!_controller.isAnimating && _controller.value < 1) {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      alignment: widget.alignment,
      child: FadeTransition(
        opacity: CurvedAnimation(parent: _controller, curve: const Interval(0, 0.4)),
        child: widget.child,
      ),
    );
  }
}

/// 指令卡：AI 指令解析命中后的生长式卡片（#12）。
/// `「task_type 星符」→ 已创建 a3f8…`（§3.6/§5.6：服务端 REST/WS chat 命中
/// instruction 时已直接建任务并回 task_uuid——卡片如实展示，不再伪造二次确认）。
class InstructionCard extends StatelessWidget {
  const InstructionCard({
    required this.taskType,
    required this.taskUuid,
    required this.title,
    this.onViewHistory,
    super.key,
  });

  final String taskType;
  final String taskUuid;
  final String title;
  final VoidCallback? onViewHistory;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final short = taskUuid.length >= 8 ? taskUuid.substring(0, 8) : taskUuid;
    return Material(
      color: palette.card,
      borderRadius: BorderRadius.circular(AstroRadius.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(AstroRadius.md),
        onTap: onViewHistory,
        child: Container(
          padding: const EdgeInsets.all(AstroSpace.card),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AstroRadius.md),
            border: Border.all(color: palette.stroke),
          ),
          child: Row(
            children: [
              Text(AstroIcons.taskRunning,
                  style: TextStyle(color: palette.aurora, fontSize: 16)),
              const SizedBox(width: AstroSpace.gapLg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$taskType → 已创建 $short',
                      style: TextStyle(
                        fontSize: AstroType.titleSm.size,
                        fontWeight: FontWeight.w500,
                        color: palette.ink900,
                      ),
                    ),
                    if (title.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: AstroType.bodySm.size,
                            color: palette.ink600,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              Text(
                AstroIcons.miscCaretRight,
                style: TextStyle(color: palette.ink400, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
