import 'package:desktop_drop/desktop_drop.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/task_schema.dart';
import 'instruction_card.dart';

/// 全局拖拽文件建任务（UX P0-4 桌面王牌入口，方案 §5.2）：
/// 拖拽监听挂壳层（禁只绑首页）；悬停=全窗 aurora 1.5dp 虚线框+中央
/// 「松手，锻成任务」提示胶囊；松手 → 弹指令卡（生长式 #12，与首页输入条
/// 共用组件族）按扩展名预填：.pdf→mineru｜.docx/.xlsx→anydoc｜.md→md2docx｜
/// URL 文本→spider_single。**确认执行，不直接开跑**（落点≠跑点）；
/// 多文件=指令卡列表可勾选批量确认；字段可编辑+「去表单精调」跳任务页预填。
class DragTaskLayer extends ConsumerStatefulWidget {
  const DragTaskLayer({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<DragTaskLayer> createState() => _DragTaskLayerState();
}

class _DragTaskLayerState extends ConsumerState<DragTaskLayer> {
  bool _hovering = false;

  static const _urlSuffixes = ['.url', '.txt', '.htm', '.html'];

  /// 拖入项 → 预填任务卡规格（扩展名映射；未命中返回 null 禁硬造）。
  _DropCardSpec? _specFor(DropItem item) {
    // DropItem extends XFile：name=文件名，path=本地路径（桌面端为文件系统路径）
    final name = item.name.toLowerCase();
    String? hit;
    if (name.endsWith('.pdf')) hit = 'mineru';
    if (name.endsWith('.docx') || name.endsWith('.doc') ||
        name.endsWith('.xlsx') || name.endsWith('.pptx')) {
      hit = 'anydoc';
    }
    if (name.endsWith('.md')) hit = 'md2docx';
    if (_urlSuffixes.any(name.endsWith)) hit = 'spider_single';
    if (hit == null) return null;
    final path = item.path;
    final spec = taskSchema.firstWhere((t) => t.type == hit!);
    final prefill = <String, dynamic>{};
    if (path.isNotEmpty) {
      prefill[hit == 'spider_single' ? 'url' : 'input_path'] = path;
    }
    return _DropCardSpec(
      taskType: hit,
      label: spec.label,
      glyph: spec.glyph,
      fileName: item.name,
      prefill: prefill,
      selected: true,
    );
  }

  Future<void> _onDrop(DropDoneDetails details) async {
    setState(() => _hovering = false);
    final specs = <_DropCardSpec>[];
    for (final item in details.files) {
      final spec = _specFor(item);
      if (spec != null) specs.add(spec);
    }
    if (specs.isEmpty || !mounted) return;
    await _confirmSheet(specs);
  }

  /// 确认执行弹层（生长式 #12 指令卡列表；可编辑字段；确认才 POST /tasks）。
  Future<void> _confirmSheet(List<_DropCardSpec> specs) async {
    final palette = AstroPaletteScope.of(context);
    final created = await showDialog<List<String>>(
      context: context,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      barrierLabel: '拖拽任务确认',
      builder: (dialogContext) => _DropConfirmDialog(specs: specs),
    );
    if (created == null || created.isEmpty || !mounted) return;
    ref.read(taskEventsProvider.notifier).taskMutated();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('${AstroIcons.taskSuccess} 已创建 ${created.length} 个任务（确认执行完成）'),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return DropTarget(
      onDragEntered: (_) => setState(() => _hovering = true),
      onDragExited: (_) => setState(() => _hovering = false),
      onDragDone: _onDrop,
      child: Stack(
        children: [
          widget.child,
          if (_hovering)
            Positioned.fill(
              child: IgnorePointer(
                child: Container(
                  margin: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AstroRadius.lg),
                    // 全窗 aurora 1.5dp 虚线框（§5.2）
                    border: Border.all(
                      color: palette.aurora,
                      width: 1.5,
                      strokeAlign: BorderSide.strokeAlignInside,
                    ),
                  ),
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                      decoration: BoxDecoration(
                        color: palette.cardRaised,
                        borderRadius:
                            BorderRadius.circular(AstroRadius.pill),
                        border: Border.all(color: palette.stroke),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(AstroIcons.taskRunning,
                              style: TextStyle(
                                  fontSize: 14, color: palette.aurora)),
                          const SizedBox(width: 8),
                          Text('松手，锻成任务',
                              style: TextStyle(
                                  fontSize: AstroType.titleSm.size,
                                  fontWeight: FontWeight.w600,
                                  color: palette.ink900)),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ---- 确认弹层（指令卡列表：勾选/编辑/确认执行/去表单精调）----

class _DropCardSpec {
  _DropCardSpec({
    required this.taskType,
    required this.label,
    required this.glyph,
    required this.fileName,
    required this.prefill,
    required this.selected,
  });

  final String taskType;
  final String label;
  final String glyph;
  final String fileName;
  final Map<String, dynamic> prefill;
  bool selected;
}

class _DropConfirmDialog extends ConsumerStatefulWidget {
  const _DropConfirmDialog({required this.specs});

  final List<_DropCardSpec> specs;

  @override
  ConsumerState<_DropConfirmDialog> createState() => _DropConfirmDialogState();
}

class _DropConfirmDialogState extends ConsumerState<_DropConfirmDialog> {
  late final List<TextEditingController> _pathCtrls = [
    for (final spec in widget.specs)
      TextEditingController(
        text: (spec.prefill['url'] ?? spec.prefill['input_path'] ?? '') as String,
      ),
  ];
  bool _submitting = false;
  String? _error;
  final List<String> _created = [];

  @override
  void dispose() {
    for (final c in _pathCtrls) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _confirmAll() async {
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    final api = ref.read(apiClientProvider);
    try {
      for (var i = 0; i < widget.specs.length; i++) {
        final spec = widget.specs[i];
        if (!spec.selected) continue;
        final config = <String, dynamic>{};
        final pathValue = _pathCtrls[i].text.trim();
        if (pathValue.isNotEmpty) {
          config[spec.taskType == 'spider_single' ? 'url' : 'input_path'] =
              pathValue;
        }
        final task = await api.createTask(spec.taskType, config,
            title: '拖拽：${spec.label}');
        final uuid = task['task_uuid'] as String?;
        if (uuid != null) _created.add(uuid);
      }
      if (!mounted) return;
      Navigator.of(context).pop(_created);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = '[${e.code}] ${e.message}';
      });
    }
  }

  void _refineInForm() {
    // 「去表单精调」（UX P1-2 非死胡同）：把首个选中项预填进任务页，
    // 字段键与确认执行一致（spider_single=url，其余=input_path）
    final spec = widget.specs.firstWhere((s) => s.selected,
        orElse: () => widget.specs.first);
    final index = widget.specs.indexOf(spec);
    final pathKey = spec.taskType == 'spider_single' ? 'url' : 'input_path';
    ref.read(taskPrefillProvider.notifier).state = TaskPrefill(
      taskType: spec.taskType,
      config: {pathKey: _pathCtrls[index].text.trim()},
      reason: '拖拽预填',
    );
    Navigator.of(context).pop(const []);
    context.go('/tasks');
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return GrowIn(
      child: Material(
        color: palette.cardRaised,
        borderRadius: BorderRadius.circular(AstroRadius.lg),
        child: Container(
          padding: const EdgeInsets.all(AstroSpace.card),
          constraints: const BoxConstraints(maxWidth: 560),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AstroRadius.lg),
            border: Border.all(color: palette.stroke),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('确认执行（落点 ≠ 跑点）',
                  style: TextStyle(
                      fontSize: AstroType.title.size,
                      fontWeight: AstroType.title.weight,
                      color: palette.ink900)),
              const SizedBox(height: 4),
              Text('按扩展名预填指令卡——勾选后确认才会创建任务',
                  style: TextStyle(
                      fontSize: AstroType.bodySm.size,
                      color: palette.ink400)),
              const SizedBox(height: AstroSpace.gapLg),
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 320),
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (var i = 0; i < widget.specs.length; i++)
                      _DropCard(
                        spec: widget.specs[i],
                        controller: _pathCtrls[i],
                        palette: palette,
                        onToggle: () => setState(() =>
                            widget.specs[i].selected =
                                !widget.specs[i].selected),
                      ),
                  ],
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: AstroSpace.gap),
                Text(_error!,
                    style: TextStyle(
                        fontSize: AstroType.bodySm.size,
                        color: palette.nova)),
              ],
              const SizedBox(height: AstroSpace.gapLg),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _refineInForm,
                    child: Text('去表单精调',
                        style: TextStyle(color: palette.ink600)),
                  ),
                  const SizedBox(width: AstroSpace.gap),
                  FilledButton.icon(
                    onPressed: _submitting ? null : _confirmAll,
                    icon: _submitting
                        ? SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation(
                                  palette.onAurora),
                            ),
                          )
                        : Text(AstroIcons.taskSuccess,
                            style: const TextStyle(fontSize: 13)),
                    label: Text(_submitting
                        ? '创建中…'
                        : '确认执行（${widget.specs.where((s) => s.selected).length}）'),
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

/// 单张指令卡（共用生长式组件族；星符+类型+可编辑路径字段+勾选）。
class _DropCard extends StatelessWidget {
  const _DropCard({
    required this.spec,
    required this.controller,
    required this.palette,
    required this.onToggle,
  });

  final _DropCardSpec spec;
  final TextEditingController controller;
  final AstroPalette palette;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: palette.card,
        borderRadius: BorderRadius.circular(AstroRadius.md),
        border: Border.all(
          color: spec.selected ? palette.aurora : palette.stroke,
          width: spec.selected ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Checkbox(value: spec.selected, onChanged: (_) => onToggle()),
              const SizedBox(width: 4),
              Text(spec.glyph,
                  style: TextStyle(fontSize: 14, color: palette.aurora)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${spec.taskType} → ${spec.label}',
                  style: TextStyle(
                      fontSize: AstroType.bodySm.size,
                      fontWeight: FontWeight.w500,
                      color: palette.ink900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          TextField(
            controller: controller,
            style: TextStyle(
                fontSize: AstroType.caption.size,
                fontFamily: AstroType.monoFamily,
                color: palette.ink900),
            decoration: InputDecoration(
              isDense: true,
              labelText: spec.fileName,
              labelStyle: TextStyle(
                  fontSize: AstroType.label.size, color: palette.ink400),
            ),
          ),
        ],
      ),
    );
  }
}
