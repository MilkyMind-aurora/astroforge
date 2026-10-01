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
/// 双钮契约（终审 L20）：
/// - 「✦ 执行」：确认创建任务——仅当服务端只解析未建单（taskUuid 空）时
///   才可点（onExecute 建单）；服务端 REST/WS chat 命中即直接建单并回
///   task_uuid（§3.6/§5.6 契约），此态按钮如实呈「已执行」，点击跳历史，
///   禁伪造二次创建。
/// - 「✧ 去表单精调」：跳任务页并预填 params（taskPrefillProvider 载荷）。
class InstructionCard extends StatelessWidget {
  const InstructionCard({
    required this.taskType,
    required this.taskUuid,
    required this.title,
    this.params = const {},
    this.onViewHistory,
    this.onExecute,
    this.onRefine,
    this.executing = false,
    super.key,
  });

  final String taskType;
  final String taskUuid;
  final String title;

  /// 解析出的参数（「去表单精调」预填载荷；空=无可预填项）。
  final Map<String, dynamic> params;
  final VoidCallback? onViewHistory;

  /// 确认创建任务（taskUuid 空时的「✦ 执行」动作）。
  final VoidCallback? onExecute;

  /// 跳任务页并预填参数（「✧ 去表单精调」动作）。
  final VoidCallback? onRefine;

  /// 执行中（onExecute 已发出，按钮 busy）。
  final bool executing;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    // 主钮前景色走 ColorScheme（AstroTheme 由 palette 构建——token 路由，
    // 夜档 onPrimaryContainer=aurora / 昼档=auroraText）
    final onTonal = Theme.of(context).colorScheme.onPrimaryContainer;
    final short = taskUuid.length >= 8 ? taskUuid.substring(0, 8) : taskUuid;
    final executed = taskUuid.isNotEmpty;
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(AstroIcons.taskRunning,
                      style: TextStyle(color: palette.aurora, fontSize: 16)),
                  const SizedBox(width: AstroSpace.gapLg),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          executed ? '$taskType → 已创建 $short' : taskType,
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
                    style: TextStyle(color: palette.ink400, fontSize: AstroType.caption.size),
                  ),
                ],
              ),
              const SizedBox(height: AstroSpace.gap),
              // 双钮行（L20）：主钮随执行态换语义；副钮恒为「去表单精调」
              Row(
                children: [
                  if (executed)
                    FilledButton.tonalIcon(
                      onPressed: onViewHistory,
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 36),
                        padding: const EdgeInsets.symmetric(horizontal: 14),
                      ),
                      icon: Text(
                        AstroIcons.miscStarRank1,
                        style: TextStyle(fontSize: AstroType.caption.size, color: onTonal),
                      ),
                      label: const Text('已执行 · 查看进度'),
                    )
                  else
                    FilledButton.tonalIcon(
                      onPressed: executing ? null : onExecute,
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(0, 36),
                        padding: const EdgeInsets.symmetric(horizontal: 14),
                      ),
                      icon: executing
                          ? SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(onTonal),
                              ),
                            )
                          : Text(
                              AstroIcons.miscStarRank1,
                              style: TextStyle(fontSize: AstroType.caption.size, color: onTonal),
                            ),
                      label: Text(executing ? '创建中…' : '执行'),
                    ),
                  const SizedBox(width: AstroSpace.gap),
                  if (onRefine != null)
                    OutlinedButton.icon(
                      onPressed: onRefine,
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(0, 36),
                        padding: const EdgeInsets.symmetric(horizontal: 14),
                      ),
                      // 星符取自 AstroIcons（icons.yaml 语义名，禁散落字符）
                      icon: Text(AstroIcons.statusHint,
                          style: TextStyle(
                              fontSize: AstroType.caption.size, color: palette.ink600)),
                      label: Text('去表单精调',
                          style: TextStyle(
                              fontSize: AstroType.bodySm.size,
                              color: palette.ink600)),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
