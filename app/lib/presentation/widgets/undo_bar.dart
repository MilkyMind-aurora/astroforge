import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 撤销倒计时进度化（§1.8 #16）：任务级重试后 10s 撤销窗——
/// 进度条 10s→0 线性 + 「撤销」按钮（撤销=取消刚创建的新任务）。
/// 数据契约如实：服务端 retry 即建任务，撤销走 cancelTask，无静默回滚伪造。
class UndoCountdownBar extends StatefulWidget {
  const UndoCountdownBar({
    required this.message,
    required this.onUndo,
    required this.onDismissed,
    this.seconds = 10,
    super.key,
  });

  final String message;
  final VoidCallback onUndo;
  final VoidCallback onDismissed;
  final int seconds;

  @override
  State<UndoCountdownBar> createState() => _UndoCountdownBarState();
}

class _UndoCountdownBarState extends State<UndoCountdownBar> {
  late int _left = widget.seconds;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _left -= 1);
      if (_left <= 0) {
        _timer?.cancel();
        widget.onDismissed();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final fraction = (_left / widget.seconds).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: palette.cardRaised,
        borderRadius: BorderRadius.circular(AstroRadius.md),
        border: Border.all(color: palette.stroke),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '${widget.message}（${_left}s 内可撤销）',
                  style: TextStyle(
                    fontSize: AstroType.bodySm.size,
                    color: palette.ink900,
                  ),
                ),
              ),
              TextButton(
                onPressed: () {
                  _timer?.cancel();
                  widget.onUndo();
                },
                child: Text('撤销', style: TextStyle(color: palette.auroraText)),
              ),
            ],
          ),
          const SizedBox(height: 6),
          // 线性 10s→0（禁曲线缓动——倒计时语义）
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: fraction,
              minHeight: 3,
              backgroundColor: palette.container,
              valueColor: AlwaysStoppedAnimation(palette.aurora),
            ),
          ),
        ],
      ),
    );
  }
}
