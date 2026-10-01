import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 状态文字推进（§1.8 #14）：状态迁移时旧字下出、新字上进——
/// AnimatedSwitcher + SlideTransition，时长 TWEEN_MOVE 250ms（tokens 唯六）。
/// reduced-motion：瞬时换字（禁运动）。
class StatusSlideText extends StatelessWidget {
  const StatusSlideText({
    required this.text,
    required this.color,
    this.style,
    this.durationMs = AstroMotion.tweenMoveMs,
    super.key,
  });

  final String text;
  final Color color;
  final TextStyle? style;
  final int durationMs;

  @override
  Widget build(BuildContext context) {
    // reduced-motion：0 时长 = 瞬时换字（AnimatedSwitcher 降级路径）
    final reduced = MediaQuery.disableAnimationsOf(context);
    return ClipRect(
      child: AnimatedSwitcher(
        duration:
            Duration(milliseconds: reduced ? 0 : durationMs),
        // reduced-motion：AnimatedSwitcher 无直关——0 时长即瞬时替换
        switchInCurve: Curves.linear,
        switchOutCurve: Curves.linear,
        transitionBuilder: (child, animation) {
          // 下出上进：入场自上方 -0.6 滑入；出场子项动画反向驱动（1→0），
          // 同一 Tween 即向下方 +0.6 滑出。
          final isIn = child.key == ValueKey(text);
          final slide = Tween<Offset>(
            begin: isIn ? const Offset(0, -0.6) : const Offset(0, 0.6),
            end: Offset.zero,
          ).animate(animation);
          return FadeTransition(
            opacity: animation,
            child: SlideTransition(position: slide, child: child),
          );
        },
        child: Text(
          text,
          key: ValueKey(text),
          style: (style ?? TextStyle(fontSize: AstroType.caption.size))
              .copyWith(color: color),
        ),
      ),
    );
  }
}
