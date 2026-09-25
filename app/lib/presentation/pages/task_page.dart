import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/task_schema.dart';
import '../widgets/context_actions.dart';
import '../widgets/liquid_chips.dart';
import '../widgets/instruction_card.dart';

/// 任务页（IA 裁决 8→5 三合一，UX 评审总裁决 / 方案 §5.5）：
/// ChoiceChip 切类型（液态指示 #3）→ schema 驱动动态表单 → 提交 → 任务卡
/// 生长式弹出（#12）。字段键=模块 CLI 真实消费键（data/task_schema.dart 基线）。
/// 延迟三档：瞬时档禁骨架屏（表单默认值即渲染，无全屏 loading）；
/// 提交为短时档（按钮 busy 变形，禁整页阻断）。
/// 模块环境缺失降级（UX P1）：env-check 对应项缺失 → 降级卡 + 提交禁用。
class TaskPage extends ConsumerStatefulWidget {
  const TaskPage({super.key});

  @override
  ConsumerState<TaskPage> createState() => _TaskPageState();
}

class _TaskPageState extends ConsumerState<TaskPage> {
  static const _axisKeys = {'x_min', 'x_max', 'y_min', 'y_max'};

  String _selected = taskSchema.first.type;
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, bool> _toggles = {};
  final Map<String, String> _dropdowns = {};
  bool _advancedOpen = false;
  bool _wpdBatch = false; // wpd：单图/批量二选一

  bool _submitting = false;
  String? _error;
  Map<String, dynamic>? _created; // 最近创建任务（任务卡展示）

  // 「最近任务」（list 区，瞬时档：REST 直查无骨架）
  List<dynamic> _recent = [];

  TaskTypeSpec get _spec =>
      taskSchema.firstWhere((t) => t.type == _selected, orElse: () => taskSchema.first);

  @override
  void initState() {
    super.initState();
    _ensureControllers(_selected);
    // 拖拽/能力胶囊预填（「去表单精调」落点；消费一次即清）
    final prefill = ref.read(taskPrefillProvider);
    if (prefill != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _applyPrefill(prefill);
        ref.read(taskPrefillProvider.notifier).state = null;
      });
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _refreshRecent();
    });
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _applyPrefill(TaskPrefill prefill) {
    setState(() {
      _selected = prefill.taskType;
      _ensureControllers(prefill.taskType);
      prefill.config.forEach((key, value) {
        final controller = _controllers['${prefill.taskType}.$key'];
        if (controller != null) {
          controller.text = '$value';
        } else if (value is bool) {
          _toggles['${prefill.taskType}.$key'] = value;
        }
      });
    });
  }

  /// 按类型惰性建控制器（默认值来自 schema，禁散落默认值副本）。
  void _ensureControllers(String type) {
    final spec = taskSchema.firstWhere((t) => t.type == type);
    for (final field in spec.fields) {
      final key = '$type.${field.key}';
      if (field.type == TaskFieldType.toggle) {
        _toggles[key] ??= field.defaultValue as bool? ?? false;
        continue;
      }
      if (field.type == TaskFieldType.template) {
        _dropdowns[key] ??= field.defaultValue as String? ?? '';
        continue;
      }
      if (_controllers.containsKey(key)) continue;
      _controllers[key] =
          TextEditingController(text: '${field.defaultValue ?? ''}');
    }
  }

  void _selectType(String type) {
    setState(() {
      _selected = type;
      _ensureControllers(type);
      _error = null;
      _advancedOpen = false;
      if (type == 'wpd') _wpdBatch = false;
    });
  }

  Future<void> _refreshRecent() async {
    try {
      final items = await ref.read(apiClientProvider).listTasks();
      if (!mounted) return;
      setState(() => _recent = items.take(5).toList());
    } on ApiError {
      // 列表失败不打断表单（瞬时档：保留旧值）
    }
  }

  /// env-check 降级判定：taskTypeEnvKeys 映射的体检项缺失 → 提交禁用+降级卡。
  Map<String, dynamic>? _missingEnvItem() {
    final envItemName = taskTypeEnvKeys[_selected];
    if (envItemName == null) return null;
    final items =
        (ref.watch(envCheckProvider).valueOrNull?['items'] as List<dynamic>?) ??
            const [];
    for (final item in items) {
      final map = (item as Map).cast<String, dynamic>();
      if ((map['name'] as String? ?? '').contains(envItemName) && map['ok'] != true) {
        return map;
      }
    }
    return null;
  }

  /// schema → 服务 config（wpd 轴字段嵌套进 axis；空可选键不下发）。
  Map<String, dynamic>? _buildConfig() {
    final spec = _spec;
    final config = <String, dynamic>{};
    final axis = <String, double>{};
    for (final field in spec.fields) {
      final key = '${spec.type}.${field.key}';
      if (_axisKeys.contains(field.key)) {
        final text = _controllers[key]?.text.trim() ?? '';
        if (text.isEmpty) continue;
        final value = double.tryParse(text);
        if (value == null) {
          setState(() => _error = '${field.label} 不是有效数字');
          return null;
        }
        axis[field.key] = value;
        continue;
      }
      switch (field.type) {
        case TaskFieldType.url:
          final url = _controllers[key]?.text.trim() ?? '';
          final problem = validateExternalUrl(url);
          if (problem != null) {
            setState(() => _error = problem);
            return null;
          }
          config['url'] = url;
        case TaskFieldType.intNumber:
          final text = _controllers[key]?.text.trim() ?? '';
          final value = int.tryParse(text);
          if (value == null) {
            setState(() => _error = '${field.label} 必须是整数');
            return null;
          }
          config[field.key] = value;
        case TaskFieldType.decimal:
          final text = _controllers[key]?.text.trim() ?? '';
          if (text.isEmpty && field.optional) continue;
          final value = double.tryParse(text);
          if (value == null) {
            setState(() => _error = '${field.label} 必须是数字');
            return null;
          }
          config[field.key] = value;
        case TaskFieldType.toggle:
          // 开关双向取值显式下发（用户关掉默认开启项时必须发送 false，
          // 禁依赖服务端默认值吞掉用户意图）
          config[field.key] = _toggles[key] ?? false;
        case TaskFieldType.directory:
          final text = _controllers[key]?.text.trim() ?? '';
          if (text.isNotEmpty) config[field.key] = text;
        case TaskFieldType.file:
          final text = _controllers[key]?.text.trim() ?? '';
          if (text.isEmpty) {
            setState(() => _error = '${field.label} 必填');
            return null;
          }
          if (spec.type == 'wpd') {
            config[_wpdBatch ? 'input_dir' : 'input_path'] = text;
          } else {
            config[field.key] = text;
          }
        case TaskFieldType.fileOrDirectory:
          final text = _controllers[key]?.text.trim() ?? '';
          if (text.isEmpty) {
            setState(() => _error = '${field.label} 必填');
            return null;
          }
          config[_wpdBatch ? 'input_dir' : 'input_path'] = text;
        case TaskFieldType.template:
          final value = _dropdowns[key];
          if (value != null && value.isNotEmpty) config[field.key] = value;
      }
    }
    if (axis.isNotEmpty) config['axis'] = axis;
    return config;
  }

  Future<void> _submit() async {
    if (_submitting) return;
    final config = _buildConfig();
    if (config == null) return;
    setState(() {
      _submitting = true;
      _error = null;
      _created = null;
    });
    try {
      final task = await ref
          .read(apiClientProvider)
          .createTask(_selected, config, title: _spec.label);
      if (!mounted) return;
      setState(() => _created = task);
      ref.read(taskEventsProvider.notifier).taskMutated();
      await _refreshRecent();
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = '[${e.code}] ${e.message}');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _pick({required bool directory, required String stateKey}) async {
    String? path;
    if (directory) {
      path = await FilePicker.getDirectoryPath();
    } else {
      final result = await FilePicker.pickFile();
      path = result?.path;
    }
    if (path == null) return;
    setState(() {
      _controllers[stateKey]?.text = path!;
    });
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final missing = _missingEnvItem();
    final deprecated = _spec.deprecated;

    return ListView(
      padding: const EdgeInsets.all(AstroSpace.section),
      children: [
        // ---- 页头 ----
        Text('任务', style: _h1(palette)),
        const SizedBox(height: 4),
        Text('爬取 · 解析 · 转换 三合一表单 —— 选类型，填参数，锻成任务。',
            style: TextStyle(fontSize: AstroType.bodySm.size, color: palette.ink600)),
        const SizedBox(height: AstroSpace.sectionLg),

        // ---- ① 功能选择（液态胶囊组，FocusTraversalGroup 区 A）----
        FocusTraversalGroup(
          child: LiquidChipRow(
            items: [
              for (final spec in taskSchema)
                LiquidChipItem(
                  key: spec.type,
                  glyph: spec.glyph,
                  label: spec.label,
                  disabled: spec.deprecated,
                  disabledNote: 'Phase 2 开发中（服务端 3006）',
                ),
            ],
            selected: _selected,
            onSelect: _selectType,
          ),
        ),
        const SizedBox(height: AstroSpace.gap),
        Text(_spec.description,
            style:
                TextStyle(fontSize: AstroType.bodySm.size, color: palette.ink400)),

        // ---- ② 环境缺失降级卡（UX P1：提交前禁用+缺失卡）----
        if (missing != null) ...[
          const SizedBox(height: AstroSpace.gapLg),
          _EnvDegradeCard(item: missing, palette: palette),
        ],

        // ---- ③ schema 动态表单（FocusTraversalGroup 区 B：表单区）----
        FocusTraversalGroup(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: AstroSpace.gapLg),
              for (final field in _spec.fields.where((f) => !f.advanced))
                _fieldRow(field, palette, deprecated: deprecated),
              // 高级折叠（「✧ 高级」行内展开）
              if (_spec.fields.any((f) => f.advanced)) ...[
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () =>
                        setState(() => _advancedOpen = !_advancedOpen),
                    child: Text(
                      '${AstroIcons.statusHint} 高级参数 ${_advancedOpen ? '收起' : '展开'}',
                      style: TextStyle(
                          fontSize: AstroType.bodySm.size,
                          color: palette.ink600),
                    ),
                  ),
                ),
                AnimatedSize(
                  duration:
                      const Duration(milliseconds: AstroMotion.tweenMoveMs),
                  curve: AstroMotion.tweenEasing,
                  alignment: Alignment.topCenter,
                  child: _advancedOpen
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            for (final field
                                in _spec.fields.where((f) => f.advanced))
                              _fieldRow(field, palette, deprecated: deprecated),
                          ],
                        )
                      : const SizedBox.shrink(),
                ),
              ],
            ],
          ),
        ),

        // ---- ④ 操作区（FocusTraversalGroup 区 C）----
        FocusTraversalGroup(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AstroSpace.section),
              // 提交钮：busy→圆形进度变形（短时档：按钮级反馈 ≤150ms）
              FilledButton.icon(
                onPressed: (_submitting || deprecated || missing != null)
                    ? null
                    : _submit,
                style: FilledButton.styleFrom(
                  minimumSize: const Size(160, 44),
                ),
                icon: _submitting
                    ? SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation(palette.onAurora),
                        ),
                      )
                    : Text(_spec.glyph, style: const TextStyle(fontSize: 14)),
                label: Text(_submitting
                    ? '提交中…'
                    : deprecated
                        ? '开发中（Phase 2）'
                        : '启动任务'),
              ),
              if (_error != null) ...[
                const SizedBox(height: AstroSpace.gap),
                Text(_error!,
                    style: TextStyle(
                        fontSize: AstroType.bodySm.size, color: palette.nova)),
              ],
            ],
          ),
        ),

        // ---- ⑤ 任务卡（生长式 #12：提交成功原地弹出）----
        if (_created != null) ...[
          const SizedBox(height: AstroSpace.gapLg),
          GrowIn(
            child: InstructionCard(
              taskType: _selected,
              taskUuid: _created!['task_uuid'] as String? ?? '',
              title: '${_spec.label} · 进度 ${_created!['progress'] ?? 0}%',
              onViewHistory: () => context.go('/history'),
            ),
          ),
          const SizedBox(height: AstroSpace.gap),
          Text(
            'Ctrl+` 打开日志面板 · Ctrl+1 切回首页',
            style: TextStyle(
                fontSize: AstroType.caption.size, color: palette.ink400),
          ),
        ],

        // ---- ⑥ 最近任务（FocusTraversalGroup 区 D：列表区；右键菜单）----
        const SizedBox(height: AstroSpace.sectionLg),
        Row(
          children: [
            Text('最近任务',
                style: TextStyle(
                    fontSize: AstroType.title.size,
                    fontWeight: AstroType.title.weight,
                    color: palette.ink900)),
            const SizedBox(width: 8),
            TextButton(
              onPressed: _refreshRecent,
              child: Text('刷新（F5）',
                  style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink400)),
            ),
          ],
        ),
        if (_recent.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AstroSpace.gap),
            child: Text('还没有任务 —— 选好类型提交，或回首页拖文件进来。',
                style: TextStyle(
                    fontSize: AstroType.bodySm.size, color: palette.ink400)),
          )
        else
          ...[
            for (final task in _recent)
              _RecentRow(
                task: (task as Map).cast<String, dynamic>(),
                palette: palette,
                onOpenHistory: () => context.go('/history'),
                onMutated: _refreshRecent,
              ),
          ],
      ],
    );
  }

  Widget _fieldRow(
    TaskFieldSpec field,
    AstroPalette palette, {
    required bool deprecated,
  }) {
    final key = '${_spec.type}.${field.key}';
    final enabled = !deprecated;
    Widget control;
    switch (field.type) {
      case TaskFieldType.url:
        control = _labeledField(
          field,
          palette,
          TextField(
            controller: _controllers[key],
            enabled: enabled,
            style: TextStyle(
                fontSize: AstroType.body.size, color: palette.ink900),
            decoration: _deco(field.label,
                hint: 'https://example.com/…', palette: palette),
          ),
        );
      case TaskFieldType.intNumber || TaskFieldType.decimal:
        control = SizedBox(
          width: 180,
          child: _labeledField(
            field,
            palette,
            TextField(
              controller: _controllers[key],
              enabled: enabled,
              keyboardType: TextInputType.number,
              style: TextStyle(
                  fontSize: AstroType.body.size, color: palette.ink900),
              decoration:
                  _deco(field.label, palette: palette),
            ),
          ),
        );
      case TaskFieldType.toggle:
        control = SwitchListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: _toggles[key] ?? false,
          onChanged: enabled
              ? (v) => setState(() => _toggles[key] = v)
              : null,
          title: Text(field.label,
              style: TextStyle(
                  fontSize: AstroType.body.size, color: palette.ink900)),
        );
      case TaskFieldType.directory:
        control = _labeledField(
          field,
          palette,
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controllers[key],
                  enabled: enabled,
                  style: TextStyle(
                      fontSize: AstroType.body.size, color: palette.ink900),
                  decoration: _deco(field.label,
                      hint: field.hint, palette: palette),
                ),
              ),
              const SizedBox(width: AstroSpace.gap),
              OutlinedButton(
                onPressed: enabled ? () => _pick(directory: true, stateKey: key) : null,
                child: const Text('选择'),
              ),
            ],
          ),
        );
      case TaskFieldType.file:
        control = _labeledField(
          field,
          palette,
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controllers[key],
                  enabled: enabled,
                  style: TextStyle(
                      fontSize: AstroType.body.size, color: palette.ink900),
                  decoration: _deco(field.label,
                      hint: field.hint ?? '选择本地文件', palette: palette),
                ),
              ),
              const SizedBox(width: AstroSpace.gap),
              OutlinedButton(
                onPressed: enabled ? () => _pick(directory: false, stateKey: key) : null,
                child: const Text('浏览'),
              ),
            ],
          ),
        );
      case TaskFieldType.fileOrDirectory:
        control = _labeledField(
          field,
          palette,
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 单图 / 批量二选一（wpd：input_path / input_dir）
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('单图')),
                  ButtonSegment(value: true, label: Text('批量目录')),
                ],
                selected: {_wpdBatch},
                onSelectionChanged: enabled
                    ? (selection) =>
                        setState(() => _wpdBatch = selection.first)
                    : null,
              ),
              const SizedBox(height: AstroSpace.gap),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controllers[key],
                      enabled: enabled,
                      style: TextStyle(
                          fontSize: AstroType.body.size, color: palette.ink900),
                      decoration: _deco(field.label,
                          hint: _wpdBatch ? '图片目录' : '单张图片', palette: palette),
                    ),
                  ),
                  const SizedBox(width: AstroSpace.gap),
                  OutlinedButton(
                    onPressed:
                        enabled ? () => _pick(directory: _wpdBatch, stateKey: key) : null,
                    child: const Text('浏览'),
                  ),
                ],
              ),
            ],
          ),
        );
      case TaskFieldType.template:
        final current = _dropdowns[key] ?? '';
        control = _labeledField(
          field,
          palette,
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: enabled ? () => _openTemplateSheet(key) : null,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      current.isEmpty ? '选择模板…' : current,
                      style: TextStyle(
                          fontSize: AstroType.body.size,
                          color: current.isEmpty
                              ? palette.ink400
                              : palette.ink900),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: AstroSpace.gapLg),
      child: control,
    );
  }

  InputDecoration _deco(String label,
      {String? hint, required AstroPalette palette}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      labelStyle: TextStyle(fontSize: AstroType.bodySm.size, color: palette.ink600),
      hintStyle:
          TextStyle(fontSize: AstroType.bodySm.size, color: palette.ink400),
    );
  }

  Widget _labeledField(
      TaskFieldSpec field, AstroPalette palette, Widget child) {
    if (field.hint == null) return child;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        child,
        const SizedBox(height: 2),
        Text(field.hint!,
            style:
                TextStyle(fontSize: AstroType.caption.size, color: palette.ink400)),
      ],
    );
  }

  /// 模板选择底部弹层（§5.5 转换页：拖回双判 #19 + 数据源 GET /templates）。
  Future<void> _openTemplateSheet(String stateKey) async {
    final api = ref.read(apiClientProvider);
    List<dynamic> templates = const [];
    String? error;
    try {
      final data = await api.listTemplates();
      templates = (data['items'] as List?) ?? const [];
    } on ApiError catch (e) {
      error = '[${e.code}] ${e.message}';
    }
    if (!mounted) return;
    final palette = AstroPaletteScope.of(context);
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: palette.cardRaised,
      barrierColor: palette.bg.withValues(alpha: 0.70),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AstroRadius.lg)),
      ),
      isScrollControlled: true,
      builder: (sheetContext) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.55,
        builder: (dragContext, scrollController) => _TemplateSheet(
          templates: templates,
          error: error,
          scrollController: scrollController,
          current: _dropdowns[stateKey] ?? '',
          onSelect: (templateKey) {
            setState(() => _dropdowns[stateKey] = templateKey);
            Navigator.of(sheetContext).pop();
          },
        ),
      ),
    );
  }

  TextStyle _h1(AstroPalette palette) => TextStyle(
        fontSize: AstroType.h1.size,
        height: AstroType.h1.height / AstroType.h1.size,
        fontWeight: AstroType.h1.weight,
        color: palette.ink900,
      );
}

// ---- 环境缺失降级卡（▲ 熔金；全系统唯一信息性描边语义族）----

class _EnvDegradeCard extends StatelessWidget {
  const _EnvDegradeCard({required this.item, required this.palette});

  final Map<String, dynamic> item;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AstroSpace.card),
      decoration: BoxDecoration(
        color: palette.container,
        borderRadius: BorderRadius.circular(AstroRadius.md),
        border: Border.all(color: palette.molten, width: 1.5),
      ),
      child: Row(
        children: [
          Text(AstroIcons.statusWarn,
              style: TextStyle(fontSize: 14, color: palette.molten)),
          const SizedBox(width: AstroSpace.gapLg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '模块环境缺失：${item['name']} —— 提交已禁用',
                  style: TextStyle(
                      fontSize: AstroType.body.size, color: palette.ink900),
                ),
                const SizedBox(height: 2),
                Text(
                  '${item['detail'] ?? ''}（体检数据：/system/env-check）',
                  style: TextStyle(
                      fontSize: AstroType.caption.size, color: palette.ink600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ---- 最近任务行（右键菜单：重试/取消/资源管理器中显示/复制 UUID）----

class _RecentRow extends StatelessWidget {
  const _RecentRow({
    required this.task,
    required this.palette,
    required this.onOpenHistory,
    required this.onMutated,
  });

  final Map<String, dynamic> task;
  final AstroPalette palette;
  final VoidCallback onOpenHistory;
  final VoidCallback onMutated;

  @override
  Widget build(BuildContext context) {
    final status = task['status'] as String? ?? 'pending';
    final (glyph, color) = statusVisual(status, palette);
    final uuid = task['task_uuid'] as String? ?? '';
    return GestureDetector(
      onSecondaryTapUp: (details) => showTaskContextMenu(
        context,
        position: details.globalPosition,
        taskUuid: uuid,
        status: status,
        outputDir: task['config']?['output_dir'] as String?,
        onMutated: onMutated,
      ),
      child: Card(
        margin: const EdgeInsets.only(bottom: AstroSpace.gap),
        child: ListTile(
          dense: true,
          leading: Text(glyph, style: TextStyle(color: color, fontSize: 16)),
          title: Text(
            '${uuid.length >= 8 ? uuid.substring(0, 8) : uuid} · ${task['task_type']}',
            style: TextStyle(
                fontSize: AstroType.bodySm.size, color: palette.ink900),
          ),
          subtitle: Text(
            '进度 ${task['progress']}%',
            style: TextStyle(
                fontSize: AstroType.caption.size, color: palette.ink600),
          ),
          trailing: TextButton(
            onPressed: onOpenHistory,
            child: Text('历史 ▸',
                style: TextStyle(
                    fontSize: AstroType.caption.size,
                    color: palette.ink400)),
          ),
        ),
      ),
    );
  }
}

// ---- 模板弹层内容 ----

class _TemplateSheet extends StatelessWidget {
  const _TemplateSheet({
    required this.templates,
    required this.error,
    required this.scrollController,
    required this.current,
    required this.onSelect,
  });

  final List<dynamic> templates;
  final String? error;
  final ScrollController scrollController;
  final String current;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Padding(
      padding: const EdgeInsets.all(AstroSpace.card),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('选择 DOCX 模板',
              style: TextStyle(
                  fontSize: AstroType.title.size,
                  fontWeight: AstroType.title.weight,
                  color: palette.ink900)),
          const SizedBox(height: AstroSpace.gap),
          if (error != null)
            Text('模板列表加载失败：$error',
                style: TextStyle(
                    fontSize: AstroType.bodySm.size, color: palette.nova))
          else
            Expanded(
              child: ListView(
                controller: scrollController,
                children: [
                  for (final raw in templates)
                    _templateTile(
                      (raw as Map).cast<String, dynamic>(),
                      context,
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _templateTile(Map<String, dynamic> t, BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final key = t['template_key'] as String? ?? '';
    final exists = t['exists'] == true;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      enabled: exists,
      leading: Text(
        AstroIcons.navConverter,
        style: TextStyle(
          fontSize: 16,
          color: exists ? palette.aurora : palette.ink400,
        ),
      ),
      title: Text(
        '${t['name']}${exists ? '' : '（文件缺失）'}',
        style: TextStyle(
            fontSize: AstroType.body.size,
            color: exists ? palette.ink900 : palette.ink400),
      ),
      subtitle: Text(
        '${t['scene'] ?? ''}',
        style: TextStyle(
            fontSize: AstroType.caption.size, color: palette.ink600),
      ),
      trailing: key == current
          ? Text(AstroIcons.taskSuccess, style: TextStyle(color: palette.aurora))
          : null,
      onTap: exists ? () => onSelect(key) : null,
    );
  }
}
