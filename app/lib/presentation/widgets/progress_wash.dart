import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 进度底色前推（§1.8 #10）：runningWashBg（aurora@6%）随 progress
/// 0→100% 自左向右填充卡底；推满瞬间提亮 160ms（TWEEN_COLOR 档）后落定。
/// 纯装饰层：置于卡内容之下（Stack 底层），不遮挡、不拦截指针。
/// reduced-motion：无前推动画，底色按当前进度直接呈现。
class ProgressWash extends StatefulWidget {
  const ProgressWash({
    required this.child,
    required this.fraction,
    super.key,
  });

  /// 卡内容（前景层）。
  final Widget child;

  /// 进度 0..1；<0 按 0，>1 按 1（推满触发提亮）。
  final double fraction;

  @override
  State<ProgressWash> createState() => _ProgressWashState();
}

class _ProgressWashState extends State<ProgressWash> {
  bool _flashDone = false;

  @override
  void didUpdateWidget(ProgressWash oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 回退（续跑/重试）后再次推满需重新提亮一拍
    if (oldWidget.fraction >= 1.0 && widget.fraction < 1.0) {
      _flashDone = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final reduced = MediaQuery.disableAnimationsOf(context);
    final fraction = widget.fraction.clamp(0.0, 1.0);
    final completed = fraction >= 1.0;
    final moveMs = reduced ? 0 : AstroMotion.tweenMoveMs;
    return ClipRRect(
      borderRadius: BorderRadius.circular(AstroRadius.md),
      child: Stack(
        children: [
          Positioned.fill(
            child: ColoredBox(color: palette.card),
          ),
          // 前推 wash：宽度按进度平滑过渡（禁整块瞬跳；reduced-motion 直达）
          Positioned.fill(
            child: Align(
              alignment: Alignment.centerLeft,
              child: TweenAnimationBuilder<double>(
                tween: Tween(end: fraction),
                duration: Duration(milliseconds: moveMs),
                curve: AstroMotion.tweenEasing,
                builder: (context, value, _) => FractionallySizedBox(
                  widthFactor: value,
                  child: ColoredBox(color: palette.runningWashBg),
                ),
              ),
            ),
          ),
          // 推满提亮 160ms：chipsSelectedBg（aurora 族 +1 档明度）闪一拍
          if (completed && !_flashDone)
            Positioned.fill(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 1.0, end: 0.0),
                duration: Duration(
                    milliseconds:
                        reduced ? 0 : AstroMotion.tweenColorMs),
                onEnd: () {
                  if (mounted) setState(() => _flashDone = true);
                },
                builder: (context, value, _) => ColoredBox(
                  color: palette.chipsSelectedBg.withValues(alpha: value),
                ),
              ),
            ),
          widget.child,
        ],
      ),
    );
  }
}
