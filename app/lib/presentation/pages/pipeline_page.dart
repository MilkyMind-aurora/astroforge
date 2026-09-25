import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';
import '../widgets/step_timeline.dart';

/// 流水线（NovaFlow 时间线，方案 §5.5）：
/// 模板卡横滚（peek 8dp）→ 分步参数（服务契约 params 为运行级全局合并，
/// 逐卡可编辑；每步预设 config 只读展示——禁伪造逐步覆盖语义）→
/// 运行时间线（垂直步骤条，失败步骤 nova+步骤级续跑钮接 MF3.5 API）。
/// 自定义 YAML 保存入口保留（折叠区，等宽编辑器）。
class PipelinePage extends ConsumerStatefulWidget {
  const PipelinePage({super.key});

  @override
  ConsumerState<PipelinePage> createState() => _PipelinePageState();
}

class _PipelinePageState extends ConsumerState<PipelinePage> {
  List<dynamic> _pipelines = [];
  Map<String, dynamic>? _selected;
  Map<String, dynamic>? _runTask; // 运行中/最近运行的流水线任务（时间线数据源）
  final Map<String, String> _paramTexts = {}; // 分步参数（JSON 文本）
  final _yamlCtrl = TextEditingController();
  bool _yamlOpen = false;
  String? _error;
  bool _starting = false;
  ForgeWebSocket? _runWs;

  @override
  void initState() {
    super.initState();
    _refresh();
    ref.listenManual(refreshEventsProvider, (_, _) => _refresh());
  }

  @override
  void dispose() {
    _yamlCtrl.dispose();
    _runWs?.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final items = await api.listPipelines();
      if (!mounted) return;
      setState(() {
        _pipelines = items;
        _error = null;
        final sel = _selected?['name'] as String?;
        if (sel == null && items.isNotEmpty) {
          _selected = (items.first as Map).cast<String, dynamic>();
        }
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  void _select(Map<String, dynamic> pipeline) {
    setState(() {
      _selected = pipeline;
      _runTask = null;
      _error = null;
    });
  }

  /// 读取分步参数文本 → 合并为运行 params（非法 JSON 提示，不硬跑）。
  Map<String, dynamic>? _collectParams() {
    final params = <String, dynamic>{};
    for (final entry in _paramTexts.entries) {
      if (entry.value.trim().isEmpty) continue;
      try {
        final decoded = jsonDecode(entry.value);
        if (decoded is Map<String, dynamic>) {
          params.addAll(decoded);
        } else {
          setState(() => _error = '${entry.key} 的参数必须是 JSON 对象');
          return null;
        }
      } on FormatException catch (e) {
        setState(() => _error = '${entry.key} 参数解析失败：${e.message}');
        return null;
      }
    }
    return params;
  }

  Future<void> _run() async {
    final selected = _selected;
    if (selected == null || _starting) return;
    final params = _collectParams();
    if (params == null) return;
    setState(() {
      _starting = true;
      _error = null;
    });
    final api = ref.read(apiClientProvider);
    try {
      final task = await api.runPipeline(
        selected['name'] as String,
        params: params,
        title: '流水线：${selected['title']}',
      );
      if (!mounted) return;
      ref.read(taskEventsProvider.notifier).taskMutated();
      final uuid = (task['task_uuid'] as String?) ?? '';
      _subscribeRun(uuid);
      setState(() {
        _starting = false;
        _runTask = (task as Map).cast<String, dynamic>();
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _starting = false;
        _error = '[${e.code}] ${e.message}';
      });
    }
  }

  /// 订阅运行任务 WS：status/progress 事件驱动时间线原位更新（禁整页轮询）。
  void _subscribeRun(String uuid) {
    if (uuid.isEmpty) return;
    _runWs?.dispose();
    final ws = ForgeWebSocket(path: '/ws/logs/$uuid')
      ..messages.listen((envelope) {
        final type = envelope['type'] as String?;
        if (type != 'status' && type != 'progress') return;
        final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>() ?? {};
        final current = _runTask;
        if (current == null || !mounted) return;
        setState(() {
          _runTask = {
            ...current,
            'status': payload['status'] as String? ?? current['status'],
            'progress': payload['progress'] ?? current['progress'],
            if (payload['steps'] != null) 'steps': payload['steps'],
          };
        });
        // status 事件载荷无步骤明细 → 变更后 REST 兜底补拉步骤状态
        if (type == 'status') _refetchRun(uuid);
      });
    ws.connect();
    _runWs = ws;
  }

  Future<void> _refetchRun(String uuid) async {
    try {
      final detail = await ref.read(apiClientProvider).taskDetail(uuid);
      if (!mounted) return;
      setState(() => _runTask = detail);
    } on ApiError {
      // 短暂不可达：保留下一次 WS 事件再补
    }
  }

  Future<void> _saveYaml() async {
    final api = ref.read(apiClientProvider);
    try {
      final parsed = await api.savePipeline(_yamlCtrl.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('${AstroIcons.taskSuccess} 模板 ${parsed['name']} 已保存'),
      ));
      _yamlCtrl.clear();
      await _refresh();
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return ListView(
      padding: const EdgeInsets.all(AstroSpace.section),
      children: [
        Text('流水线',
            style: TextStyle(
                fontSize: AstroType.h1.size,
                fontWeight: AstroType.h1.weight,
                color: palette.ink900)),
        const SizedBox(height: 4),
        Text('NovaFlow 编排引擎 · 模板持久化于 PostgreSQL',
            style: TextStyle(
                fontSize: AstroType.bodySm.size, color: palette.ink600)),
        const SizedBox(height: AstroSpace.sectionLg),

        // ---- ① 模板卡横滚（peek 8dp）----
        if (_error != null) ...[
          Text('加载失败：$_error',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.nova)),
          const SizedBox(height: AstroSpace.gap),
        ],
        if (_pipelines.isEmpty && _error == null)
          Text('暂无模板 —— 可在下方 YAML 折叠区保存自定义模板。',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.ink400))
        else
          FocusTraversalGroup(
            child: SizedBox(
              height: 108,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                // peek 8dp：首尾 padding 让相邻卡边缘露出（§5.5）
                padding: const EdgeInsets.symmetric(vertical: 4),
                itemCount: _pipelines.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, index) =>
                    _PipelineCard(
                  pipeline: (_pipelines[index] as Map).cast<String, dynamic>(),
                  selected: _selected?['name'] ==
                      (_pipelines[index] as Map)['name'],
                  palette: palette,
                  onSelect: () => _select(
                      (_pipelines[index] as Map).cast<String, dynamic>()),
                ),
              ),
            ),
          ),

        // ---- ② 分步参数 ----
        if (_selected != null) ...[
          const SizedBox(height: AstroSpace.section),
          Text('${_selected!['title']} · 分步参数',
              style: TextStyle(
                  fontSize: AstroType.title.size,
                  fontWeight: AstroType.title.weight,
                  color: palette.ink900)),
          const SizedBox(height: AstroSpace.gap),
          Text(
            '参数为运行级合并（服务契约 params 随任务下发）；每步预设 config 只读展示。',
            style: TextStyle(
                fontSize: AstroType.caption.size, color: palette.ink400),
          ),
          const SizedBox(height: AstroSpace.gapLg),
          FocusTraversalGroup(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final raw
                    in (_selected!['steps'] as List? ?? const []))
                  _StepParamCard(
                    step: (raw as Map).cast<String, dynamic>(),
                    palette: palette,
                    paramText: _paramTexts[raw['name'] as String? ?? ''] ?? '',
                    onParamChanged: (text) => setState(
                        () => _paramTexts[raw['name'] as String? ?? ''] = text),
                  ),
              ],
            ),
          ),

          // ---- ③ 运行钮 ----
          const SizedBox(height: AstroSpace.section),
          FocusTraversalGroup(
            child: Row(
              children: [
                FilledButton.icon(
                  onPressed: _starting ? null : _run,
                  style: FilledButton.styleFrom(
                      minimumSize: const Size(140, 44)),
                  icon: _starting
                      ? SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation(palette.onAurora),
                          ),
                        )
                      : Text(AstroIcons.navPipeline,
                          style: const TextStyle(fontSize: 14)),
                  label: Text(_starting ? '启动中…' : '运行流水线'),
                ),
                if (_error != null) ...[
                  const SizedBox(width: AstroSpace.gapLg),
                  Expanded(
                    child: Text(_error!,
                        style: TextStyle(
                            fontSize: AstroType.bodySm.size,
                            color: palette.nova)),
                  ),
                ],
              ],
            ),
          ),
        ],

        // ---- ④ 运行时间线 ----
        if (_runTask != null) ...[
          const SizedBox(height: AstroSpace.section),
          _RunTimelineCard(task: _runTask!, palette: palette),
        ],

        // ---- ⑤ 自定义 YAML（折叠区；Monaco 级编辑器后期——方案 §5.5）----
        const SizedBox(height: AstroSpace.sectionLg),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: () => setState(() => _yamlOpen = !_yamlOpen),
            child: Text(
              '${AstroIcons.statusHint} 自定义 YAML ${_yamlOpen ? '收起' : '展开'}',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.ink600),
            ),
          ),
        ),
        AnimatedSize(
          duration: const Duration(milliseconds: AstroMotion.tweenMoveMs),
          curve: AstroMotion.tweenEasing,
          alignment: Alignment.topCenter,
          child: _yamlOpen
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _yamlCtrl,
                      maxLines: 8,
                      style: TextStyle(
                        fontFamily: AstroType.monoFamily,
                        fontSize: AstroType.bodySm.size,
                        color: palette.ink900,
                      ),
                      decoration: const InputDecoration(
                        hintText: 'name: my_pipeline\ntitle: 我的流水线\nsteps:\n  - name: 步骤一\n    task_type: mineru\n    module: mineru',
                      ),
                    ),
                    const SizedBox(height: AstroSpace.gap),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        onPressed: _saveYaml,
                        icon: const Icon(Icons.save_outlined, size: 16),
                        label: const Text('保存模板'),
                      ),
                    ),
                  ],
                )
              : const SizedBox.shrink(),
        ),
      ],
    );
  }
}

// ---- 模板卡（横滚；选中=chipsSelectedBg wash+aurora 描边）----

class _PipelineCard extends StatelessWidget {
  const _PipelineCard({
    required this.pipeline,
    required this.selected,
    required this.palette,
    required this.onSelect,
  });

  final Map<String, dynamic> pipeline;
  final bool selected;
  final AstroPalette palette;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    final steps = (pipeline['steps'] as List? ?? const []).length;
    return GestureDetector(
      onTap: onSelect,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: AstroMotion.tweenColorMs),
        width: 252,
        padding: const EdgeInsets.all(AstroSpace.card),
        decoration: BoxDecoration(
          color: selected ? palette.chipsSelectedBg : palette.card,
          borderRadius: BorderRadius.circular(AstroRadius.md),
          border: Border.all(
            color: selected ? palette.aurora : palette.stroke,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  pipeline['is_builtin'] == true
                      ? AstroIcons.statusOk
                      : AstroIcons.miscStarMid,
                  style: TextStyle(
                      fontSize: 12,
                      color: selected ? palette.auroraText : palette.ink400),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text('${pipeline['title']}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontSize: AstroType.titleSm.size,
                          fontWeight: FontWeight.w600,
                          color: palette.ink900)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Expanded(
              child: Text('${pipeline['description']}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink600)),
            ),
            Text('$steps 个步骤',
                style: TextStyle(
                    fontSize: AstroType.caption.size,
                    color: palette.ink400)),
          ],
        ),
      ),
    );
  }
}

// ---- 分步参数卡 ----

class _StepParamCard extends StatefulWidget {
  const _StepParamCard({
    required this.step,
    required this.palette,
    required this.paramText,
    required this.onParamChanged,
  });

  final Map<String, dynamic> step;
  final AstroPalette palette;
  final String paramText;
  final ValueChanged<String> onParamChanged;

  @override
  State<_StepParamCard> createState() => _StepParamCardState();
}

class _StepParamCardState extends State<_StepParamCard> {
  bool _open = false;
  late final TextEditingController _paramCtrl =
      TextEditingController(text: widget.paramText);

  @override
  void didUpdateWidget(_StepParamCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 外部预填变更（本步参数由父层持有），仅当文本不同步时回填，避免光标跳动
    if (widget.paramText != oldWidget.paramText &&
        widget.paramText != _paramCtrl.text) {
      _paramCtrl.text = widget.paramText;
    }
  }

  @override
  void dispose() {
    _paramCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    final preset = widget.step['config'] as Map? ?? const {};
    return Card(
      margin: const EdgeInsets.only(bottom: AstroSpace.gap),
      child: Padding(
        padding: const EdgeInsets.all(AstroSpace.card),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => setState(() => _open = !_open),
              child: Row(
                children: [
                  Text(
                    (widget.step['status'] as String?) == 'success'
                        ? AstroIcons.taskSuccess
                        : AstroIcons.taskPending,
                    style: TextStyle(
                        fontSize: 12, color: palette.auroraText),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('${widget.step['name']}',
                        style: TextStyle(
                            fontSize: AstroType.titleSm.size,
                            fontWeight: FontWeight.w500,
                            color: palette.ink900)),
                  ),
                  Text('${widget.step['task_type']}',
                      style: TextStyle(
                          fontSize: AstroType.caption.size,
                          color: palette.ink400)),
                  const SizedBox(width: 8),
                  Text(
                    _open ? AstroIcons.miscCaretDown : AstroIcons.miscCaretRight,
                    style:
                        TextStyle(fontSize: 11, color: palette.ink400),
                  ),
                ],
              ),
            ),
            AnimatedSize(
              duration:
                  const Duration(milliseconds: AstroMotion.tweenMoveMs),
              curve: AstroMotion.tweenEasing,
              alignment: Alignment.topCenter,
              child: !_open
                  ? const SizedBox.shrink()
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: AstroSpace.gap),
                        if (preset.isNotEmpty) ...[
                          Text('预设 config（只读）',
                              style: TextStyle(
                                  fontSize: AstroType.caption.size,
                                  color: palette.ink400)),
                          const SizedBox(height: 4),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: palette.sunken,
                              borderRadius:
                                  BorderRadius.circular(AstroRadius.sm),
                            ),
                            child: Text(
                              const JsonEncoder.withIndent('  ').convert(preset),
                              style: TextStyle(
                                fontFamily: AstroType.monoFamily,
                                fontSize: AstroType.caption.size,
                                color: palette.ink600,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: AstroSpace.gap),
                        TextField(
                          controller: _paramCtrl,
                          maxLines: 3,
                          style: TextStyle(
                            fontFamily: AstroType.monoFamily,
                            fontSize: AstroType.bodySm.size,
                            color: palette.ink900,
                          ),
                          decoration: const InputDecoration(
                            hintText: '{"key": "value"} 本步参数（JSON，留空跳过）',
                          ),
                          onChanged: widget.onParamChanged,
                        ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---- 运行时间线卡 ----

class _RunTimelineCard extends StatelessWidget {
  const _RunTimelineCard({required this.task, required this.palette});

  final Map<String, dynamic> task;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final status = task['status'] as String? ?? 'pending';
    final uuid = task['task_uuid'] as String? ?? '';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AstroSpace.card),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('运行时间线',
                    style: TextStyle(
                        fontSize: AstroType.title.size,
                        fontWeight: AstroType.title.weight,
                        color: palette.ink900)),
                const SizedBox(width: AstroSpace.gap),
                Text('$uuid · ${task['progress'] ?? 0}% · $status',
                    style: TextStyle(
                        fontFamily: AstroType.monoFamily,
                        fontSize: AstroType.caption.size,
                        color: palette.ink400)),
                const Spacer(),
                Text(
                  'Ctrl+` 看日志',
                  style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink400),
                ),
              ],
            ),
            // 真实进度条（progress 字段，禁伪造）
            const SizedBox(height: AstroSpace.gap),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: ((task['progress'] as num?)?.toDouble() ?? 0) / 100,
                minHeight: 3,
                backgroundColor: palette.container,
                valueColor: AlwaysStoppedAnimation(palette.aurora),
              ),
            ),
            const SizedBox(height: AstroSpace.gapLg),
            StepTimeline(
              steps: (task['steps'] as List?) ?? const [],
              taskUuid: uuid,
              onStepRetried: (_) {},
            ),
          ],
        ),
      ),
    );
  }
}
