import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';

/// 步骤时间线（星空设计系统规格 §三.5，流水线运行视图 + 任务详情共用）：
/// 节点圆 20 / 连接线 2dp；pending=1.5dp stroke ink-400 空心；
/// running=aurora 环 + 内点 6dp 呼吸 1.6s；done=aurora 实底 ✓；
/// failed=nova 实底 + 行 wash + 步骤级续跑钮（UX P0-2 显式文案，接 MF3.5 API）；
/// 完成过冲 +8% 回弹 ζ0.6（#11，SPRING_POP 同族 ζ）。
class StepTimeline extends StatelessWidget {
  const StepTimeline({
    required this.steps,
    required this.taskUuid,
    this.onStepRetried,
    this.compact = false,
    super.key,
  });

  /// 服务任务步骤（task_scheduler 步骤字典：step_index/step_name/status）。
  final List<dynamic> steps;
  final String taskUuid;

  /// 步骤级续跑成功后回调（调用方刷新任务详情）。
  final void Function(Map<String, dynamic> record)? onStepRetried;

  /// 紧凑模式（任务页任务卡内：不带续跑钮）。
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < steps.length; i++)
          _StepRow(
            step: (steps[i] as Map).cast<String, dynamic>(),
            isLast: i == steps.length - 1,
            palette: palette,
            taskUuid: taskUuid,
            compact: compact,
            onStepRetried: onStepRetried,
          ),
      ],
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.step,
    required this.isLast,
    required this.palette,
    required this.taskUuid,
    required this.compact,
    this.onStepRetried,
  });

  final Map<String, dynamic> step;
  final bool isLast;
  final AstroPalette palette;
  final String taskUuid;
  final bool compact;
  final void Function(Map<String, dynamic> record)? onStepRetried;

  @override
  Widget build(BuildContext context) {
    final status = step['status'] as String? ?? 'pending';
    final index = (step['step_index'] as num?)?.toInt() ?? 0;
    final name = step['step_name'] as String? ?? '';
    final failed = status == 'failed';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _NodeIcon(status: status, palette: palette),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                '${index + 1}. $name',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: AstroType.bodySm.size,
                  color: failed ? palette.nova : palette.ink900,
                ),
              ),
            ),
            _StatusTag(status: status, palette: palette),
          ],
        ),
        // 失败步骤显式续跑契约（禁裸「重试」；与任务级 retry=裂变新任务区分）
        if (failed && !compact) ...[
          Padding(
            padding: const EdgeInsets.only(left: 30, top: 2, bottom: 4),
            child: _StepRetryButton(
              taskUuid: taskUuid,
              stepIndex: index,
              stepName: name,
              palette: palette,
              onDone: onStepRetried,
            ),
          ),
        ],
        if (!isLast)
          Padding(
            padding: const EdgeInsets.only(left: 9.5),
            child: Container(
              width: 2,
              height: 18,
              color: palette.faint,
            ),
          ),
      ],
    );
  }
}

/// 步骤级续跑（POST /tasks/{uuid}/steps/{index}/retry，MF3.5）：
/// 文案契约「从步骤 N『{name}』继续（前 N-1 步产物已保留）」。
class _StepRetryButton extends StatelessWidget {
  const _StepRetryButton({
    required this.taskUuid,
    required this.stepIndex,
    required this.stepName,
    required this.palette,
    this.onDone,
  });

  final String taskUuid;
  final int stepIndex;
  final String stepName;
  final AstroPalette palette;
  final void Function(Map<String, dynamic> record)? onDone;

  Future<void> _resume(BuildContext context) async {
    final api = ProviderScope.containerOf(context).read(apiClientProvider);
    try {
      final record = await api.retryTaskStep(taskUuid, stepIndex);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
            '${AstroIcons.taskRunning} 任务原地续跑（uuid 不变）：${record['status']}'),
      ));
      onDone?.call(record.cast<String, dynamic>());
    } on ApiError catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // 错误码语义映射（§1.1）：1001 参数=nova 族文案；4001 资源=熔金族。
    return Tooltip(
      message: '仅失败/取消任务的失败或未运行步骤可续跑；'
          '返回体 task_uuid 不变（原地更新）',
      child: TextButton(
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          minimumSize: const Size(0, 28),
        ),
        onPressed: () => _resume(context),
        child: Text(
          '从步骤 ${stepIndex + 1}『$stepName』继续（前 $stepIndex 步产物已保留）',
          style: TextStyle(fontSize: AstroType.caption.size, color: palette.nova),
        ),
      ),
    );
  }
}

class _NodeIcon extends StatefulWidget {
  const _NodeIcon({required this.status, required this.palette});

  final String status;
  final AstroPalette palette;

  @override
  State<_NodeIcon> createState() => _NodeIconState();
}

class _NodeIconState extends State<_NodeIcon> with SingleTickerProviderStateMixin {
  late final AnimationController _pop = AnimationController(vsync: this);

  @override
  void didUpdateWidget(_NodeIcon oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 步骤完成瞬间：scale 过冲 1.08 → 回弹落定（#11 ζ0.6）
    if (oldWidget.status != 'success' && widget.status == 'success') {
      final stiffness = AstroMotion.springPop.stiffness;
      final spring = SpringDescription(
        mass: 1,
        stiffness: stiffness,
        damping: AstroMotion.springPop.damping * 2 * math.sqrt(stiffness),
      );
      _pop.animateWith(SpringSimulation(spring, 0, 1, 0));
    }
  }

  @override
  void dispose() {
    _pop.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    final status = widget.status;
    final Widget node;
    switch (status) {
      case 'success':
        node = Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(color: palette.aurora, shape: BoxShape.circle),
          child: Center(
            child: Text(
              AstroIcons.taskSuccess,
              style: TextStyle(fontSize: 11, color: palette.onAurora),
            ),
          ),
        );
      case 'failed':
        node = Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(color: palette.nova, shape: BoxShape.circle),
          child: Center(
            child: Text(
              AstroIcons.taskFailed,
              style: TextStyle(fontSize: 10, color: palette.onNova),
            ),
          ),
        );
      case 'running':
        node = const _RunningNode();
      case 'canceled':
        node = Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: palette.ink400, width: 1.5),
          ),
          child: Center(
            child: Text(
              AstroIcons.taskCanceled,
              style: TextStyle(fontSize: 9, color: palette.ink400),
            ),
          ),
        );
      default: // pending：1.5dp stroke ink-400 空心（规格 §三.5 修正值 5.62）
        node = Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: palette.ink400, width: 1.5),
          ),
        );
    }
    return AnimatedBuilder(
      animation: _pop,
      builder: (context, child) {
        // 过冲：1 → 1.08（前 40% 冲过）→ 1（回弹由 spring 物理给出）
        final t = _pop.value;
        final scale = t == 0 ? 1.0 : 1.0 + 0.08 * math.sin(t * math.pi) * (1 - t * 0.4);
        return Transform.scale(scale: scale, child: child);
      },
      child: node,
    );
  }
}

/// running 节点：aurora 环 + 内点 6dp 呼吸 1.6s（reduced-motion 静态环）。
class _RunningNode extends StatefulWidget {
  const _RunningNode();

  @override
  State<_RunningNode> createState() => _RunningNodeState();
}

class _RunningNodeState extends State<_RunningNode>
    with SingleTickerProviderStateMixin {
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _breath.stop();
    } else {
      _breath.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return AnimatedBuilder(
      animation: _breath,
      builder: (context, _) => Container(
        width: 20,
        height: 20,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: palette.aurora, width: 1.5),
        ),
        child: Center(
          child: Container(
            width: 6 + 2 * _breath.value,
            height: 6 + 2 * _breath.value,
            decoration: BoxDecoration(
              color: palette.aurora.withValues(alpha: 0.5 + 0.5 * _breath.value),
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}

class _StatusTag extends StatelessWidget {
  const _StatusTag({required this.status, required this.palette});

  final String status;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final (text, color) = switch (status) {
      'success' => ('完成', palette.auroraText),
      'failed' => ('失败', palette.nova),
      'running' => ('运行中', palette.auroraText),
      'canceled' => ('已取消', palette.ink400),
      _ => ('待运行', palette.ink400),
    };
    return Text(
      text,
      style: TextStyle(fontSize: AstroType.caption.size, color: color),
    );
  }
}
