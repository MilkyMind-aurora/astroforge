import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../core/mascot/starling_view.dart';
import '../../data/api_client/dio_client.dart';
import '../shell/astro_shortcuts.dart';
import '../widgets/instruction_card.dart';

/// 首页 = 对话式入口（Kimi 新会话式 · AstroForge 的品牌时刻，方案 §5.2）：
/// 空态四元素淡入上移 stagger（星仔→问候→胶囊→输入条）；
/// 输入条聚焦光晕 = 全 App 唯一活光（#26）；引擎休眠降级（UX P0-1）；
/// 服务不可达 → 壳内嵌连接引导（UX P0-5）。
class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

enum _EngineGate { unknown, ready, asleep, waking, wakeFailed }

class _HomePageState extends ConsumerState<HomePage> {
  final _composer = TextEditingController();
  final _focusNode = FocusNode();
  bool _focused = false;

  _EngineGate _engine = _EngineGate.unknown;
  Timer? _wakeTimer;
  Timer? _elapsedTimer;
  int _wakeElapsedS = 0;
  String? _wakeError;
  int? _conversationId;

  // 一次性交互结果（指令卡 / 闲聊分流 / 追问 chips）
  Map<String, dynamic>? _instruction;
  String? _chatReply;
  String? _chatNotice;
  bool _sending = false;
  String? _sendError;

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(() {
      if (mounted) setState(() => _focused = _focusNode.hasFocus);
    });
    _probeEngine();
    // env-check（健康点 + 首页体检胶囊共用）
    Future<void>.microtask(() => ref.read(envCheckProvider.notifier).refresh());
  }

  @override
  void dispose() {
    _wakeTimer?.cancel();
    _elapsedTimer?.cancel();
    _composer.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _probeEngine() async {
    setState(() => _engine = _EngineGate.unknown);
    try {
      final status = await ref.read(apiClientProvider).engineStatus();
      if (!mounted) return;
      setState(() => _engine =
          status['reachable'] == true ? _EngineGate.ready : _EngineGate.asleep);
    } on ApiError catch (_) {
      if (!mounted) return;
      setState(() => _engine = _EngineGate.asleep);
    }
  }

  /// 唤醒引擎（UX P0-1）：轮询引擎进程出现（≤60s）→ 触发默认模型加载。
  /// 服务核心只探测不拉起进程（watcher.probe_status）——点火卡如实呈现等待。
  Future<void> _wakeEngine() async {
    _wakeTimer?.cancel();
    _elapsedTimer?.cancel();
    setState(() {
      _engine = _EngineGate.waking;
      _wakeElapsedS = 0;
      _wakeError = null;
    });
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _wakeElapsedS++);
    });
    // 退避 1s→2s→4s→8s 封顶，持续探测至 60s（§5.1 轮询纪律）
    var delayS = 1;
    var waited = 0;
    var reachable = false;
    while (waited <= 60) {
      try {
        final status = await ref.read(apiClientProvider).engineStatus();
        if (status['reachable'] == true) {
          reachable = true;
          break;
        }
      } on ApiError {
        // 服务核心本身不可达：继续等（服务可能也在冷启动）
      }
      await Future<void>.delayed(Duration(seconds: delayS));
      waited += delayS;
      delayS = (delayS * 2).clamp(1, 8);
    }
    _elapsedTimer?.cancel();
    if (!mounted) return;
    if (!reachable) {
      setState(() {
        _engine = _EngineGate.wakeFailed;
        _wakeError = '60s 内未探测到星伴引擎（引擎进程未运行）';
      });
      return;
    }
    // 引擎进程在位 → 加载默认模型（qwen2b「常驻 · 日常指令」）
    try {
      await ref.read(apiClientProvider).switchModel('qwen2b');
      if (!mounted) return;
      setState(() => _engine = _EngineGate.ready);
      // 唤醒成功后自动送出输入条中保留的话
      final text = _composer.text.trim();
      if (text.isNotEmpty) await _send();
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _engine = _EngineGate.wakeFailed;
        _wakeError = '[${e.code}] ${e.message}';
      });
    }
  }

  /// 能力胶囊 → 任务页预填（IA 8→5：采集/解析/转换三合一「任务」页）。
  void _goTasks(String taskType, Map<String, dynamic> config) {
    ref.read(taskPrefillProvider.notifier).state =
        TaskPrefill(taskType: taskType, config: config, reason: '能力胶囊');
    context.go('/tasks');
  }

  void _cancelWake() {
    _wakeTimer?.cancel();
    _elapsedTimer?.cancel();
    setState(() {
      _engine = _EngineGate.asleep;
      _wakeError = null;
    });
  }

  Future<void> _send() async {
    final message = _composer.text.trim();
    if (message.isEmpty || _sending) return;
    if (_engine != _EngineGate.ready) {
      await _wakeEngine();
      return;
    }
    setState(() {
      _sending = true;
      _sendError = null;
      _instruction = null;
      _chatReply = null;
      _chatNotice = null;
    });
    try {
      final resp = await ref
          .read(apiClientProvider)
          .aiChat(message, conversationId: _conversationId);
      if (!mounted) return;
      setState(() {
        _sending = false;
        _conversationId = resp['conversation_id'] as int?;
        final instruction = resp['instruction'] as Map<String, dynamic>?;
        if (instruction != null) {
          // 指令命中：服务端已建任务（task_uuid 如实展示）
          _instruction = instruction;
          final uuid = resp['task_uuid'] as String?;
          ref.read(taskEventsProvider.notifier).taskMutated();
          _composer.clear();
          if (uuid != null) _instruction!['task_uuid'] = uuid;
        } else {
          // 闲聊分流（UX P0-6）：不硬造任务卡
          _chatReply = (resp['reply'] as String?) ?? '';
          _chatNotice = (resp['notice'] as String?) ??
              '这不像一条任务指令——可改写成动作句，或直接使用下方能力胶囊';
        }
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        // 引擎在发送瞬间掉线 → 回休眠态（发送钮变唤醒引擎）
        _engine = e.code == 4004 ? _EngineGate.asleep : _engine;
        _sendError = '[${e.code}] ${e.message}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final health = ref.watch(envCheckProvider);
    final healthData = health.valueOrNull;

    return Actions(
      actions: {
        FocusComposerIntent: CallbackAction<FocusComposerIntent>(
          onInvoke: (_) {
            _focusNode.requestFocus();
            return null;
          },
        ),
        SendIntent: CallbackAction<SendIntent>(
          onInvoke: (_) {
            _send();
            return null;
          },
        ),
      },
      child: Stack(
        children: [
          // 服务不可达 → 壳内嵌连接引导（P0-5：品牌先行，骨架占位，无整页跳转）
          health.hasError ? _ConnectGuide(onRecovered: () {
            ref.read(envCheckProvider.notifier).refresh();
            ref.read(connectionProvider.notifier).nudgeReconnect();
          }) : _buildEmptyState(context, palette, healthData),
          // 右上角体检胶囊（9/9 ✦；异常时熔金 7/9 ▲，点击展开九宫格卡）。
          // 顶层留给壳层仪表胶囊（IA 裁决：监控常驻位），体检胶囊下移一档。
          Positioned(
            top: AstroSpace.window + 44,
            right: AstroSpace.window,
            child: _EnvBadge(data: healthData, palette: palette),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(
    BuildContext context,
    AstroPalette palette,
    Map<String, dynamic>? healthData,
  ) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          child: SizedBox(
            height: constraints.maxHeight,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 640),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // ---- 品牌时刻：星仔 + 问候（空态四元素 stagger 淡入上移）----
                    Center(
                      child: _StaggerIn(
                        delay: const Duration(milliseconds: 0),
                        child: const StarlingView(size: 120),
                      ),
                    ),
                    const SizedBox(height: AstroSpace.gapLg),
                    _StaggerIn(
                      delay: const Duration(milliseconds: 150),
                      child: Text(
                        '今天要把什么，锻成秩序？',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: AstroType.display.size,
                          height: AstroType.display.height / AstroType.display.size,
                          fontWeight: AstroType.display.weight,
                          color: palette.ink900,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    _StaggerIn(
                      delay: const Duration(milliseconds: 300),
                      child: Text(
                        '爬文档、解 PDF、转 Word，交给衍星台。',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: AstroType.bodySm.size,
                          color: palette.ink600,
                        ),
                      ),
                    ),
                    const SizedBox(height: AstroSpace.section),
                    // ---- 能力胶囊横排（表单路径不依赖 AI，始终可用）----
                    _StaggerIn(
                      delay: const Duration(milliseconds: 450),
                      child: Center(
                        child: Wrap(
                          spacing: AstroSpace.gap,
                          runSpacing: AstroSpace.gap,
                          alignment: WrapAlignment.center,
                          children: [
                            _Capability(
                              glyph: AstroIcons.navSpider,
                              label: '爬取文档站',
                              onTap: () => _goTasks('spider_single', const {}),
                            ),
                            _Capability(
                              glyph: AstroIcons.navParser,
                              label: '解析 PDF',
                              onTap: () => _goTasks('mineru', const {}),
                            ),
                            _Capability(
                              glyph: AstroIcons.navConverter,
                              label: '转 Word',
                              onTap: () => _goTasks('md2docx', const {}),
                            ),
                            _Capability(
                              glyph: AstroIcons.navPipeline,
                              label: '流水线',
                              onTap: () => context.go('/pipeline'),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: AstroSpace.gapLg),
                    // ---- 输入条（唯一活光 #26）----
                    _StaggerIn(
                      delay: const Duration(milliseconds: 600),
                      child: _Composer(
                        controller: _composer,
                        focusNode: _focusNode,
                        focused: _focused,
                        engine: _engine,
                        sending: _sending,
                        wakeElapsedS: _wakeElapsedS,
                        wakeError: _wakeError,
                        onSend: _send,
                        onWake: _wakeEngine,
                        onCancelWake: _cancelWake,
                        onRetryWake: _wakeEngine,
                      ),
                    ),
                    if (_sendError != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        _sendError!,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: AstroType.bodySm.size, color: palette.nova),
                      ),
                    ],
                    // ---- 指令卡 / 闲聊分流 ----
                    if (_instruction != null) ...[
                      const SizedBox(height: AstroSpace.gapLg),
                      GrowIn(
                        child: InstructionCard(
                          taskType: _instruction!['task_type'] as String? ?? '',
                          taskUuid: _instruction!['task_uuid'] as String? ?? '',
                          title: _instruction!['title'] as String? ?? '',
                          onViewHistory: () => context.go('/history'),
                        ),
                      ),
                    ],
                    if (_chatReply != null) ...[
                      const SizedBox(height: AstroSpace.gapLg),
                      Container(
                        padding: const EdgeInsets.all(AstroSpace.card),
                        decoration: BoxDecoration(
                          color: palette.container.withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(AstroRadius.md),
                        ),
                        child: Text(
                          _chatReply!,
                          style: TextStyle(
                            fontSize: AstroType.body.size,
                            height: AstroType.body.height / AstroType.body.size,
                            color: palette.ink900,
                          ),
                        ),
                      ),
                    ],
                    if (_chatNotice != null) ...[
                      const SizedBox(height: AstroSpace.gap),
                      Text(
                        _chatNotice!,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: AstroType.bodySm.size, color: palette.ink600),
                      ),
                    ],
                    const SizedBox(height: AstroSpace.gapLg),
                    // 合规行
                    Text(
                      '本地引擎驱动 · 数据不出本机',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: AstroType.caption.size, color: palette.ink400),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

// ---- 空态错峰入场（#13：translateY 16→0 + fade，stagger 150ms）----

class _StaggerIn extends StatefulWidget {
  const _StaggerIn({required this.child, required this.delay});

  final Widget child;
  final Duration delay;

  @override
  State<_StaggerIn> createState() => _StaggerInState();
}

class _StaggerInState extends State<_StaggerIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    Future<void>.delayed(widget.delay, () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // reduced-motion：错峰入场瞬时到位（星仔规格 §五 降级表）
    if (MediaQuery.disableAnimationsOf(context)) {
      _controller.value = 1.0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final t = Curves.easeOutCubic.transform(_controller.value);
        return Opacity(
          opacity: t,
          child: Transform.translate(offset: Offset(0, 16 * (1 - t)), child: child),
        );
      },
      child: widget.child,
    );
  }
}

// ---- 能力胶囊（低对比 ink-600，hover 升 ink-900）----

class _Capability extends StatefulWidget {
  const _Capability({
    required this.glyph,
    required this.label,
    required this.onTap,
  });

  final String glyph;
  final String label;
  final VoidCallback onTap;

  @override
  State<_Capability> createState() => _CapabilityState();
}

class _CapabilityState extends State<_Capability> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: InkWell(
        onTap: widget.onTap,
        borderRadius: BorderRadius.circular(AstroRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: _hover ? palette.container : palette.bg.withValues(alpha: 0),
            borderRadius: BorderRadius.circular(AstroRadius.pill),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(widget.glyph,
                  style: TextStyle(
                      color: _hover ? palette.ink900 : palette.ink600,
                      fontSize: 13)),
              const SizedBox(width: 6),
              Text(
                widget.label,
                style: TextStyle(
                  fontSize: AstroType.bodySm.size,
                  color: _hover ? palette.ink900 : palette.ink600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- 输入条（h52 R999；聚焦=aurora 1.5dp + 8%→12% 光晕呼吸 2.4s，唯一活光）----

class _Composer extends StatefulWidget {
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.focused,
    required this.engine,
    required this.sending,
    required this.wakeElapsedS,
    required this.wakeError,
    required this.onSend,
    required this.onWake,
    required this.onCancelWake,
    required this.onRetryWake,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool focused;
  final _EngineGate engine;
  final bool sending;
  final int wakeElapsedS;
  final String? wakeError;
  final VoidCallback onSend;
  final VoidCallback onWake;
  final VoidCallback onCancelWake;
  final VoidCallback onRetryWake;

  @override
  State<_Composer> createState() => _ComposerState();
}

class _ComposerState extends State<_Composer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _glow;

  @override
  void initState() {
    super.initState();
    // 唯一活光呼吸：仅聚焦期运行（失焦即停表，不让 AnimatedBuilder 空转 60fps）
    _glow = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400), // 2.4s 呼吸
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // reduced-motion：光晕不做呼吸，聚焦静态 8%（唯一活光降级）
    if (MediaQuery.disableAnimationsOf(context)) {
      _glow.stop();
    } else if (widget.focused && !_glow.isAnimating) {
      _glow.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(_Composer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.focused != oldWidget.focused) {
      if (widget.focused &&
          !MediaQuery.disableAnimationsOf(context) &&
          !_glow.isAnimating) {
        _glow.repeat(reverse: true);
      } else if (!widget.focused) {
        _glow.stop();
      }
    }
  }

  @override
  void dispose() {
    _glow.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final asleep = widget.engine == _EngineGate.asleep ||
        widget.engine == _EngineGate.wakeFailed;
    final waking = widget.engine == _EngineGate.waking;
    final canSend = widget.engine == _EngineGate.ready &&
        widget.controller.text.trim().isNotEmpty &&
        !widget.sending;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 引擎点火卡（唤醒期：模型名+已等待时长+可取消，禁伪造 GB 进度）
        if (waking) ...[
          _IgnitionCard(
            elapsedS: widget.wakeElapsedS,
            onCancel: widget.onCancelWake,
          ),
          const SizedBox(height: 8),
        ],
        if (widget.engine == _EngineGate.wakeFailed) ...[
          Row(
            children: [
              Expanded(
                child: Text(
                  widget.wakeError ?? '唤醒失败',
                  style: TextStyle(
                      fontSize: AstroType.bodySm.size, color: palette.nova),
                ),
              ),
              TextButton(
                onPressed: widget.onRetryWake,
                child: Text('重试', style: TextStyle(color: palette.auroraText)),
              ),
            ],
          ),
          const SizedBox(height: 8),
        ],
        AnimatedBuilder(
          animation: _glow,
          builder: (context, child) {
            // 唯一活光：聚焦时 aurora 8%→12% 呼吸（规格 §三.2；非聚焦 0）
            final glowBase = widget.focused ? 0.08 : 0.0;
            final glow = glowBase + (widget.focused ? 0.04 * _glow.value : 0.0);
            return Container(
              height: 52,
              decoration: BoxDecoration(
                color: palette.card,
                borderRadius: BorderRadius.circular(AstroRadius.pill),
                border: Border.all(
                  color: widget.focused ? palette.aurora : palette.stroke,
                  width: widget.focused ? 1.5 : 1.0,
                ),
                boxShadow: [
                  if (glow > 0)
                    BoxShadow(
                      color: palette.aurora.withValues(alpha: glow),
                      blurRadius: 16,
                      spreadRadius: 1,
                    ),
                ],
              ),
              child: Row(
                children: [
                  const SizedBox(width: 18),
                  Expanded(
                    child: TextField(
                      controller: widget.controller,
                      focusNode: widget.focusNode,
                      style: TextStyle(
                          fontSize: AstroType.body.size, color: palette.ink900),
                      cursorColor: palette.aurora,
                      decoration: InputDecoration.collapsed(
                        hintText: asleep
                            ? '星伴引擎休眠中——输入将唤醒（约 30s）或直接使用上方能力胶囊'
                            : '用一句话描述任务…',
                        hintStyle: TextStyle(
                            fontSize: AstroType.bodySm.size,
                            color: palette.ink400),
                      ),
                      onSubmitted: (_) => widget.onSend(),
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(width: 8),
                  _SendButton(
                    asleep: asleep,
                    waking: waking,
                    sending: widget.sending,
                    canSend: canSend,
                    hasText: widget.controller.text.trim().isNotEmpty,
                    onSend: widget.onSend,
                    onWake: widget.onWake,
                  ),
                  const SizedBox(width: 8),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

/// 发送钮三态（规格 §三.3）：禁用 container 底 ink-400；可用 aurora 实底
/// onAurora 星符；休眠=「唤醒引擎」可显式触发（绝不禁用无解释）。
class _SendButton extends StatelessWidget {
  const _SendButton({
    required this.asleep,
    required this.waking,
    required this.sending,
    required this.canSend,
    required this.hasText,
    required this.onSend,
    required this.onWake,
  });

  final bool asleep;
  final bool waking;
  final bool sending;
  final bool canSend;
  final bool hasText;
  final VoidCallback onSend;
  final VoidCallback onWake;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    if (asleep) {
      // 唤醒引擎态：显式加载+可取消语义（文字钮形式，高度 36 命中≥40 由父容器保证）
      return ConstrainedBox(
        constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
        child: TextButton(
          onPressed: waking ? null : onWake,
          child: Text(
            '唤醒引擎',
            style: TextStyle(
              fontSize: AstroType.bodySm.size,
              color: palette.auroraText,
            ),
          ),
        ),
      );
    }
    return SizedBox(
      width: 44,
      height: 44,
      child: IconButton.filled(
        tooltip: '发送（Ctrl+Enter）',
        onPressed: canSend ? onSend : null,
        style: IconButton.styleFrom(
          backgroundColor: canSend ? palette.aurora : palette.container,
        ),
        icon: sending
            ? SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation(palette.onAurora),
                ),
              )
            : Icon(
                LucideIcons.sendHorizontal,
                size: 18,
                color: canSend ? palette.onAurora : palette.ink400,
              ),
      ),
    );
  }
}

/// 引擎点火卡（UX P0：模型冷启动是独立仪式；进度不伪造——只报真实已等待时长）。
class _IgnitionCard extends StatelessWidget {
  const _IgnitionCard({required this.elapsedS, required this.onCancel});

  final int elapsedS;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: palette.aiContainerBg,
        borderRadius: BorderRadius.circular(AstroRadius.md),
      ),
      child: Row(
        children: [
          Text(AstroIcons.aiThinking,
              style: TextStyle(color: palette.nebula, fontSize: 14)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '引擎点火 · qwen2b（常驻 · 日常指令）· 已等待 ${elapsedS}s · 预计 ≈30s',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.ink900),
            ),
          ),
          TextButton(
            onPressed: onCancel,
            child: Text('取消', style: TextStyle(color: palette.ink600)),
          ),
        ],
      ),
    );
  }
}

// ---- 体检胶囊（9/9 ✦；异常熔金 7/9 ▲；点击展开九宫格卡）----

class _EnvBadge extends StatelessWidget {
  const _EnvBadge({required this.data, required this.palette});

  final Map<String, dynamic>? data;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final data = this.data;
    if (data == null) return const SizedBox.shrink();
    final okCount = (data['ok_count'] as num?)?.toInt() ?? 0;
    final total = (data['total'] as num?)?.toInt() ?? 0;
    final allOk = okCount >= total && total > 0;
    return InkWell(
      borderRadius: BorderRadius.circular(AstroRadius.pill),
      onTap: () => _openDetail(context),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: palette.card.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(AstroRadius.pill),
          border: Border.all(color: palette.stroke),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '$okCount/$total',
              style: TextStyle(
                fontSize: AstroType.bodySm.size,
                fontWeight: FontWeight.w500,
                color: allOk ? palette.auroraText : palette.moltenText,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              allOk ? AstroIcons.navHome : AstroIcons.statusWarn,
              style: TextStyle(
                fontSize: 12,
                color: allOk ? palette.auroraText : palette.molten,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _openDetail(BuildContext context) {
    final data = this.data;
    if (data == null) return;
    showDialog<void>(
      context: context,
      builder: (dialogContext) {
        final palette = AstroPaletteScope.of(dialogContext);
        final items = (data['items'] as List<dynamic>? ?? const []);
        return AlertDialog(
          backgroundColor: palette.cardRaised,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AstroRadius.lg),
          ),
          title: Text('环境体检',
              style: TextStyle(
                  fontSize: AstroType.h2.size, color: palette.ink900)),
          content: SizedBox(
            width: 420,
            child: Wrap(
              spacing: AstroSpace.gap,
              runSpacing: AstroSpace.gap,
              children: [
                for (final item in items)
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 126),
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: palette.container,
                        borderRadius: BorderRadius.circular(AstroRadius.sm),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${item['ok'] == true ? AstroIcons.statusOk : AstroIcons.statusError} '
                            '${item['name']}',
                            style: TextStyle(
                              fontSize: AstroType.bodySm.size,
                              color: item['ok'] == true
                                  ? palette.ink900
                                  : palette.nova,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${item['detail'] ?? ''}',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: AstroType.caption.size,
                              color: palette.ink600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text('收起', style: TextStyle(color: palette.ink600)),
            ),
          ],
        );
      },
    );
  }
}

// ---- 壳内嵌连接引导（UX P0-5：品牌先行 + 阶段化反馈 + 失败诊断卡）----

class _ConnectGuide extends ConsumerStatefulWidget {
  const _ConnectGuide({required this.onRecovered});

  final VoidCallback onRecovered;

  @override
  ConsumerState<_ConnectGuide> createState() => _ConnectGuideState();
}

class _ConnectGuideState extends ConsumerState<_ConnectGuide> {
  static const _stages = ['激活环境', '端口监听', '数据库握手', '就绪'];

  Timer? _pollTimer;
  int _elapsedS = 0;
  int _stage = 0;
  int _pollToken = 0;
  bool _launching = false;
  String? _diagnostic;

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    final token = ++_pollToken;
    setState(() {
      _elapsedS = 0;
      _stage = 0;
      _diagnostic = null;
    });
    // 退避 1s→2s→4s→8s 封顶，持续轮询至 60s（§5.1；实测冷启动 10~30s）
    var delayS = 1;
    var waited = 0;
    Future<void> poll() async {
      while (waited <= 60 && mounted && token == _pollToken) {
        try {
          final health = await ref.read(apiClientProvider).health();
          if (!mounted) return;
          // 阶段推断（禁伪造进度）：端口监听=health 可达；数据库握手=db=true
          setState(() {
            _stage = health['db'] == true ? 3 : 2;
          });
          widget.onRecovered();
          return;
        } on ApiError {
          setState(() {
            _stage = waited == 0 ? 0 : 1; // 激活环境→端口监听
            _elapsedS = waited;
          });
        }
        await Future<void>.delayed(Duration(seconds: delayS));
        waited += delayS;
        delayS = (delayS * 2).clamp(1, 8);
      }
      if (mounted) {
        setState(() => _diagnostic =
            '60s 内未连上 Sidereal Core（127.0.0.1:8420）。'
            '可一键拉起服务，或查看服务日志 scripts/data/logs/service.log。');
      }
    }

    unawaited(poll());
  }

  /// 一键拉起服务（Windows：scripts/start_service.bat；macOS：start_service.sh）。
  /// 脚本路径可经 ASTROFORGE_START_SCRIPT 覆盖；拉起失败如实展示 stderr 尾行。
  Future<void> _launchService() async {
    setState(() {
      _launching = true;
      _diagnostic = null;
    });
    try {
      final script = Platform.environment['ASTROFORGE_START_SCRIPT'] ??
          (Platform.isWindows
              ? 'scripts\\start_service.bat'
              : 'scripts/start_service.sh');
      final process = await Process.start(
        script,
        const [],
        runInShell: true,
        workingDirectory: Directory.current.path,
      );
      final stderrLines = <String>[];
      process.stderr.transform(utf8.decoder).listen((chunk) {
        stderrLines.addAll(chunk.split('\n'));
        if (stderrLines.length > 20) stderrLines.removeRange(0, stderrLines.length - 20);
      });
      final code = await process.exitCode;
      if (!mounted) return;
      setState(() {
        _launching = false;
        _diagnostic = code == 0
            ? '拉起脚本已执行（退出码 0），继续等待服务就绪…'
            : '拉起失败（退出码 $code）\n${stderrLines.take(5).join('\n')}';
      });
      _startPolling();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _launching = false;
        _diagnostic = '无法执行启动脚本：$e';
      });
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 460),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const StarlingView(size: 96, state: StarlingState.sleeping),
            const SizedBox(height: AstroSpace.gapLg),
            Text(
              'Sidereal Core 未响应',
              style: TextStyle(
                fontSize: AstroType.h2.size,
                fontWeight: AstroType.h2.weight,
                color: palette.ink900,
              ),
            ),
            const SizedBox(height: AstroSpace.gap),
            // 阶段化反馈四段（禁伪造进度——按 health 探活结果推断）
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < _stages.length; i++) ...[
                  Text(
                    '${i <= _stage ? AstroIcons.statusOk : AstroIcons.taskPending} ${_stages[i]}',
                    style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: i <= _stage ? palette.auroraText : palette.ink400,
                    ),
                  ),
                  if (i < _stages.length - 1)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 6),
                      child: Text('·',
                          style: TextStyle(color: palette.ink400, fontSize: 11)),
                    ),
                ],
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '已等待 ${_elapsedS}s · 127.0.0.1:8420',
              style: TextStyle(
                  fontSize: AstroType.caption.size, color: palette.ink400),
            ),
            const SizedBox(height: AstroSpace.section),
            FilledButton.icon(
              onPressed: _launching ? null : _launchService,
              icon: _launching
                  ? SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(LucideIcons.rocket, size: 16),
              label: Text(_launching ? '拉起中…' : '一键拉起服务'),
            ),
            const SizedBox(height: AstroSpace.gap),
            TextButton(
              onPressed: _startPolling,
              child: Text('重新探测', style: TextStyle(color: palette.ink600)),
            ),
            if (_diagnostic != null) ...[
              const SizedBox(height: AstroSpace.gapLg),
              // nova 红诊断卡（失败分支：stderr 尾 5 行 + 复制诊断）
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AstroSpace.card),
                decoration: BoxDecoration(
                  color: palette.errorWashBg,
                  borderRadius: BorderRadius.circular(AstroRadius.md),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _diagnostic!,
                      style: TextStyle(
                          fontSize: AstroType.bodySm.size, color: palette.ink900),
                    ),
                    const SizedBox(height: AstroSpace.gap),
                    TextButton.icon(
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: _diagnostic!));
                      },
                      icon: const Icon(LucideIcons.copy, size: 14),
                      label: Text('复制诊断信息',
                          style: TextStyle(
                              fontSize: AstroType.bodySm.size,
                              color: palette.ink600)),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
