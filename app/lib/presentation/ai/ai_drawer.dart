import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_highlight/themes/atom-one-dark.dart';
import 'package:flutter_highlight/themes/github.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:markdown_widget/markdown_widget.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../core/mascot/starling_view.dart';
import '../../data/ai/stream_batcher.dart';
import '../../data/api_client/dio_client.dart';
import '../../data/ws_client/ws_client.dart';
import '../shell/astro_shortcuts.dart';
import '../widgets/instruction_card.dart';
import 'model_sheet.dart';

/// 星伴 AI 抽屉（§5.6 右侧 SlidingDrawer）：
/// - 流式 #5 合批：ai_delta 先入缓冲，33ms 帧节流增量 append 到单条消息的
///   ValueNotifier——AnimatedBuilder 局部刷新，禁整列 setState（§1.8 #5）；
/// - 消息流：用户右对齐胶囊（container 底 max 78%），星伴无气泡，回复体
///   Markdown 渲染 + 代码高亮（终审 L19：markdown_widget，配色取主题 token）；
/// - 思考卡 `✶ 思忖中` 三点错相（#6：1.2s 循环错相 0.2s）+ 已思考秒数；
/// - 回复完成后操作行（复制/重新生成，18dp 线性图标）+ 追问 chips（错峰 60ms）；
/// - 指令卡生长式（#12，L20 双钮）；闲聊分流（UX P0-6）禁硬造任务卡；
/// - 模型弹层两档（Kimi 同构，§5.6）；头部收起钮 #24 汉堡→叉 AnimatedIcons。
class AiDrawer extends ConsumerStatefulWidget {
  const AiDrawer({super.key});

  @override
  ConsumerState<AiDrawer> createState() => _AiDrawerState();
}

enum AiMessageState { thinking, streaming, done, error }

class _AiMessage {
  _AiMessage.user(String text)
      : isUser = true,
        textNotifier = ValueNotifier<String>(text),
        state = AiMessageState.done;

  _AiMessage.assistant()
      : isUser = false,
        textNotifier = ValueNotifier<String>(''),
        state = AiMessageState.thinking,
        startedAt = DateTime.now();

  final bool isUser;
  final ValueNotifier<String> textNotifier;
  AiMessageState state;
  Map<String, dynamic>? instruction;
  String? notice;
  bool executing = false; // 指令卡「执行」钮 busy（L20）
  DateTime startedAt = DateTime.now();
}

class _AiDrawerState extends ConsumerState<AiDrawer> {
  // 修复基线 bug①：TextEditingController 移出 build（旧实现每次重建丢输入）
  final _composer = TextEditingController();
  final _focusNode = FocusNode();
  final _scroll = ScrollController();
  final _messages = <_AiMessage>[];

  ForgeWebSocket? _aiWs;
  Timer? _flushTimer;
  final _streamBuffer = StreamBatcher();
  int? _conversationId;
  String _currentModel = 'qwen2b';
  bool _switchingModel = false;
  bool _connected = false;

  @override
  void initState() {
    super.initState();
    _connectWs();
    _probeModel();
  }

  Future<void> _probeModel() async {
    try {
      final status = await ref.read(apiClientProvider).engineStatus();
      if (!mounted) return;
      final model = status['current_model'] as String?;
      if (model != null && model.isNotEmpty) {
        setState(() => _currentModel = model);
      }
    } on ApiError {
      // 引擎不可达：模型胶囊仍可打开弹层（切档时才报错）
    }
  }

  void _connectWs() {
    _aiWs?.dispose();
    final ws = ForgeWebSocket(path: '/ws/ai');
    ws.status.addListener(() {
      if (!mounted) return;
      setState(() => _connected = ws.status.value == WsStatus.connected);
    });
    ws.messages.listen(_onAiEnvelope);
    ws.connect();
    _aiWs = ws;
  }

  // ---- 流式合批（#5）：帧节流增量 append，禁逐 delta setState ----

  void _startFlushTimer() {
    _flushTimer ??= Timer.periodic(const Duration(milliseconds: 33), (_) {
      _drainBuffer();
    });
  }

  void _drainBuffer() {
    // 帧内合批量：≥4 字起步；积压大时按 1/8 加速排空（T_STREAM 2~4 token/帧同族）
    final chunk = _streamBuffer.drain();
    if (chunk.isEmpty) return;
    final last = _lastAssistant();
    if (last == null) return;
    last.state = AiMessageState.streaming;
    last.textNotifier.value += chunk; // 单条 ValueNotifier → AnimatedBuilder 局部刷新
    _scrollToBottom();
  }

  void _onAiEnvelope(Map<String, dynamic> envelope) {
    final type = envelope['type'] as String?;
    final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>() ?? {};
    final conversationId = payload['conversation_id'] as int?;
    if (conversationId != null && _conversationId == null) {
      _conversationId = conversationId;
    }
    switch (type) {
      case 'ai_start':
        if (!mounted) return;
        setState(() {
          _messages.add(_AiMessage.user(payload['message'] as String? ?? ''));
          _messages.add(_AiMessage.assistant());
        });
        _startFlushTimer();
        _scrollToBottom();
      case 'ai_delta':
        _streamBuffer.add(payload['text'] as String? ?? '');
      case 'ai_done':
        _stopFlush();
        if (!mounted) return;
        setState(() {
          final last = _lastAssistant();
          if (last != null) {
            // 服务端最终 reply 兜底（合批丢帧时以全量为准）
            last.textNotifier.value =
                payload['reply'] as String? ?? last.textNotifier.value;
            last.state = AiMessageState.done;
            last.instruction = payload['instruction'] as Map<String, dynamic>?;
            final taskUuid = payload['task_uuid'] as String?;
            if (taskUuid != null) {
              last.instruction ??= {'task_uuid': taskUuid};
              ref.read(taskEventsProvider.notifier).taskMutated();
            }
            // 闲聊分流（P0-6）：ai_done.instruction=null 即分流信号，前端不硬造任务卡
            if (last.instruction == null) {
              last.notice = (payload['notice'] as String?) ??
                  '这不像一条任务指令——试试说「把 Vue 文档爬下来转 Word」';
            }
          }
        });
        _scrollToBottom();
      case 'ai_error':
        _stopFlush();
        if (!mounted) return;
        setState(() {
          final last = _lastAssistant();
          if (last != null) {
            last.state = AiMessageState.error;
            last.notice = payload['message'] as String? ?? 'AI 引擎不可达';
          }
        });
    }
  }

  void _stopFlush() {
    _flushTimer?.cancel();
    _flushTimer = null;
    _drainBuffer();
  }

  _AiMessage? _lastAssistant() {
    for (final message in _messages.reversed) {
      if (!message.isUser) return message;
    }
    return null;
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
      }
    });
  }

  void _send() {
    final message = _composer.text.trim();
    if (message.isEmpty) return;
    _sendText(message);
    _composer.clear();
  }

  /// 追问 chips / 重新生成共用的发送入口（不改输入框内容）。
  void _sendText(String message) {
    if (!_connected) {
      _connectWs();
      // 通道未就绪：本地插入降级回执（连接恢复后需重发）
      setState(() {
        _messages.add(_AiMessage.user(message));
        final fallback = _AiMessage.assistant()
          ..state = AiMessageState.error
          ..notice = '星伴通道未连接——服务核心不可达或 token 失效';
        _messages.add(fallback);
      });
      _scrollToBottom();
      return;
    }
    // 连接态：消息体上 WS，服务端 ai_start 回显补用户行（含 conversation_id）
    _aiWs?.send({
      'message': message,
      if (_conversationId != null) 'conversation_id': _conversationId,
    });
  }

  /// 重新生成（L19 操作行）：以该回复的前一条用户消息重发。
  void _regenerate(_AiMessage assistantMessage) {
    final index = _messages.indexOf(assistantMessage);
    if (index <= 0) return;
    for (var i = index - 1; i >= 0; i--) {
      if (_messages[i].isUser) {
        final text = _messages[i].textNotifier.value.trim();
        if (text.isNotEmpty) _sendText(text);
        return;
      }
    }
  }

  /// 指令卡「✦ 执行」（L20）：仅「已解析未建单」路径（taskUuid 空）可达——
  /// 服务端 REST/WS 命中即建单并回 task_uuid，此入口当前为将来「仅解析」
  /// 契约预留；现路由下按钮如实呈「已执行」态（见 InstructionCard 注释）。
  Future<void> _executeInstruction(_AiMessage message) async {
    final instruction = message.instruction;
    if (instruction == null || message.executing) return;
    final taskType = instruction['task_type'] as String? ?? '';
    if (taskType.isEmpty || (instruction['task_uuid'] as String?)?.isNotEmpty == true) {
      return;
    }
    setState(() => message.executing = true);
    try {
      final task = await ref.read(apiClientProvider).createTask(
            taskType,
            (instruction['params'] as Map?)?.cast<String, dynamic>() ?? {},
            title: instruction['title'] as String?,
          );
      if (!mounted) return;
      setState(() {
        message.executing = false;
        instruction['task_uuid'] = task['task_uuid'] as String? ?? '';
      });
      ref.read(taskEventsProvider.notifier).taskMutated();
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => message.executing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('[${e.code}] ${e.message}')),
      );
    }
  }

  /// 指令卡「✧ 去表单精调」（L20）：预填 params 跳任务页。
  void _refineInstruction(_AiMessage message) {
    final instruction = message.instruction;
    if (instruction == null) return;
    ref.read(taskPrefillProvider.notifier).state = TaskPrefill(
      taskType: instruction['task_type'] as String? ?? '',
      config: (instruction['params'] as Map?)?.cast<String, dynamic>() ?? const {},
      reason: '指令卡精调',
    );
    context.go('/tasks');
  }

  Future<void> _switchModel(String modelKey) async {
    setState(() => _switchingModel = true);
    try {
      await ref.read(apiClientProvider).switchModel(modelKey);
      if (!mounted) return;
      setState(() => _currentModel = modelKey);
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('[${e.code}] ${e.message}')),
      );
    } finally {
      if (mounted) setState(() => _switchingModel = false);
    }
  }

  @override
  void dispose() {
    _flushTimer?.cancel();
    _aiWs?.dispose();
    for (final message in _messages) {
      message.textNotifier.dispose();
    }
    _composer.dispose();
    _focusNode.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Drawer(
      width: 460,
      backgroundColor: palette.card,
      child: SafeArea(
        child: Column(
          children: [
            _Header(
              palette: palette,
              currentModel: _currentModel,
              switching: _switchingModel,
              connected: _connected,
              onSwitchModel: _switchModel,
            ),
            Divider(height: 1, color: palette.faint.withValues(alpha: 0.7)),
            Expanded(
              child: _messages.isEmpty
                  ? const _EmptyState()
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.all(AstroSpace.card),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) => _MessageRow(
                        message: _messages[index],
                        palette: palette,
                        onViewHistory: () => context.go('/history'),
                        onRegenerate: () => _regenerate(_messages[index]),
                        onRefine: () => _refineInstruction(_messages[index]),
                        onExecute: () => _executeInstruction(_messages[index]),
                        onSendText: _sendText,
                      ),
                    ),
            ),
            Divider(height: 1, color: palette.faint.withValues(alpha: 0.7)),
            _ComposerBar(
              palette: palette,
              composer: _composer,
              onSend: _send,
            ),
          ],
        ),
      ),
    );
  }
}

// ---- 头部：银河饰线（白名单位）+ 星仔 + 模型胶囊 ----

class _Header extends StatelessWidget {
  const _Header({
    required this.palette,
    required this.currentModel,
    required this.switching,
    required this.connected,
    required this.onSwitchModel,
  });

  final AstroPalette palette;
  final String currentModel;
  final bool switching;
  final bool connected;
  final ValueChanged<String> onSwitchModel;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
          AstroSpace.card, AstroSpace.card, AstroSpace.card, 10),
      child: Row(
        children: [
          // 银河渐变饰线（白名单位 ai_drawer_headline：180° 垂直 3×40dp）
          Container(
            width: 3,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AstroRadius.pill),
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                stops: AstroGalaxy.positions,
                colors: AstroPaletteScope.darkProgressOf(context) >= 0.5
                    ? AstroGalaxy.darkStops
                    : AstroGalaxy.lightStops,
              ),
            ),
          ),
          const SizedBox(width: AstroSpace.gapLg),
          const StarlingView(size: 28),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '星伴',
                style: TextStyle(
                  fontSize: AstroType.title.size,
                  fontWeight: FontWeight.w500,
                  color: palette.ink900,
                ),
              ),
              Text(
                connected ? '星伴在线 · 本地引擎' : '星伴通道连接中…',
                style: TextStyle(
                    fontSize: AstroType.caption.size, color: palette.ink400),
              ),
            ],
          ),
          const Spacer(),
          _ModelCapsule(
            label: modelDisplayName(currentModel),
            busy: switching,
            palette: palette,
            onTap: () => showModelSheet(
              context,
              currentModel: currentModel,
              busy: switching,
              onSelect: onSwitchModel,
            ),
          ),
          // #24 汉堡变叉：抽屉内收起钮（勾账表裁定落位）——开抽屉瞬间
          // menu→close 形变 250ms（TWEEN_MOVE 档），点按收起抽屉
          const _DrawerCloseButton(),
        ],
      ),
    );
  }
}

/// #24 汉堡→叉（AnimatedIcons.menu_close）：挂载即播形变（抽屉滑入
/// 同步完成），点按收起抽屉；reduced-motion 直接呈现叉态。
class _DrawerCloseButton extends StatefulWidget {
  const _DrawerCloseButton();

  @override
  State<_DrawerCloseButton> createState() => _DrawerCloseButtonState();
}

class _DrawerCloseButtonState extends State<_DrawerCloseButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _morph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: AstroMotion.tweenMoveMs),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _morph.value = 1.0;
    } else if (!_morph.isAnimating && _morph.value < 1) {
      _morph.forward();
    }
  }

  @override
  void dispose() {
    _morph.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Tooltip(
      message: '收起星伴（Ctrl+Shift+A 再开）',
      child: IconButton(
        onPressed: () => Navigator.of(context).pop(),
        icon: AnimatedIcon(
          icon: AnimatedIcons.menu_close,
          progress: _morph,
          color: palette.ink600,
          size: 20,
        ),
      ),
    );
  }
}

class _ModelCapsule extends StatelessWidget {
  const _ModelCapsule({
    required this.label,
    required this.busy,
    required this.palette,
    required this.onTap,
  });

  final String label;
  final bool busy;
  final AstroPalette palette;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AstroRadius.pill),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: palette.aiContainerBg, // nebula@14% on card（规格 §三.8）
          borderRadius: BorderRadius.circular(AstroRadius.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              busy ? '$label · 引擎忙…' : label,
              style: TextStyle(
                fontSize: AstroType.bodySm.size,
                fontWeight: FontWeight.w500,
                color: palette.nebulaText,
              ),
            ),
            const SizedBox(width: 4),
            Text(
              AstroIcons.miscCaretDown,
              style: TextStyle(fontSize: AstroType.label.size, color: palette.nebulaText),
            ),
          ],
        ),
      ),
    );
  }
}

// ---- 空态：星仔 + 引导句（§5.6）----

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const StarlingView(size: 96),
          const SizedBox(height: AstroSpace.gapLg),
          Text(
            '问我「把 Vue 文档爬下来转 Word」试试',
            style: TextStyle(
                fontSize: AstroType.bodySm.size, color: palette.ink600),
          ),
        ],
      ),
    );
  }
}

// ---- 消息行：用户右对齐胶囊（max 78%）；星伴无气泡 Markdown 回复体 ----

class _MessageRow extends StatelessWidget {
  const _MessageRow({
    required this.message,
    required this.palette,
    required this.onViewHistory,
    required this.onRegenerate,
    required this.onRefine,
    required this.onExecute,
    required this.onSendText,
  });

  final _AiMessage message;
  final AstroPalette palette;
  final VoidCallback onViewHistory;
  final VoidCallback onRegenerate;
  final VoidCallback onRefine;
  final VoidCallback onExecute;

  /// 追问 chip 直接发送（与输入条等效）。
  final ValueChanged<String> onSendText;

  @override
  Widget build(BuildContext context) {
    if (message.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.78),
          decoration: BoxDecoration(
            color: palette.container,
            borderRadius: BorderRadius.circular(AstroRadius.pill),
          ),
          child: ValueListenableBuilder<String>(
            valueListenable: message.textNotifier,
            builder: (context, text, _) => Text(
              text,
              style: TextStyle(
                fontSize: AstroType.body.size,
                height: AstroType.body.height / AstroType.body.size,
                color: palette.ink900,
              ),
            ),
          ),
        ),
      );
    }
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (message.state == AiMessageState.thinking)
            _ThinkingDots(palette: palette)
          else if (message.state == AiMessageState.error)
            // 错误回执保持纯文本（nova，非 Markdown 语义）
            ValueListenableBuilder<String>(
              valueListenable: message.textNotifier,
              builder: (context, text, _) => Text(
                text,
                style: TextStyle(
                  fontSize: AstroType.body.size,
                  height: AstroType.body.height / AstroType.body.size,
                  color: palette.nova,
                ),
              ),
            )
          else
            // 星伴回复 Markdown 渲染（L19）：流式期间逐帧重解析（消息体量小，
            // 33ms 合批节奏下开销可忽略）；代码块高亮主题随昼夜档切换
            ValueListenableBuilder<String>(
              valueListenable: message.textNotifier,
              builder: (context, text, _) => AiMarkdownReply(
                text: text,
                palette: palette,
              ),
            ),
          if (message.notice != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                children: [
                  Text(AstroIcons.statusHint,
                      style: TextStyle(color: palette.ink400, fontSize: AstroType.caption.size)),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      message.notice!,
                      style: TextStyle(
                          fontSize: AstroType.bodySm.size,
                          color: palette.ink600),
                    ),
                  ),
                ],
              ),
            ),
          // 操作行（L19）：复制 / 重新生成（18dp 线性图标）——完成后才可操作
          if (message.state == AiMessageState.done &&
              message.textNotifier.value.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _MessageAction(
                    tooltip: '复制回复',
                    icon: LucideIcons.copy,
                    palette: palette,
                    onTap: () {
                      Clipboard.setData(
                          ClipboardData(text: message.textNotifier.value));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('回复已复制')),
                      );
                    },
                  ),
                  const SizedBox(width: 4),
                  _MessageAction(
                    tooltip: '重新生成',
                    icon: LucideIcons.refreshCw,
                    palette: palette,
                    onTap: onRegenerate,
                  ),
                ],
              ),
            ),
          // 追问 chips（L19）：错峰 60ms 上浮——命中任务给动作跳转，
          // 闲聊给可发送的示例追问（客户端建议，非伪造 AI 输出）
          if (message.state == AiMessageState.done &&
              message.textNotifier.value.isNotEmpty) ...[
            const SizedBox(height: 6),
            _FollowUpChips(
              palette: palette,
              suggestions: _followUps(),
              onSelected: _onFollowUp,
            ),
          ],
          if (message.instruction?['task_type'] != null) ...[
            const SizedBox(height: AstroSpace.gap),
            GrowIn(
              alignment: Alignment.topLeft,
              child: InstructionCard(
                taskType: message.instruction!['task_type'] as String? ?? '',
                taskUuid: message.instruction!['task_uuid'] as String? ?? '',
                title: message.instruction!['title'] as String? ?? '',
                params: (message.instruction!['params'] as Map?)
                        ?.cast<String, dynamic>() ??
                    const {},
                onViewHistory: onViewHistory,
                onRefine: onRefine,
                onExecute: onExecute,
                executing: message.executing,
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 追问建议（上下文派生，客户端固定文案——禁伪造 AI 生成内容）。
  List<String> _followUps() {
    if (message.instruction?['task_type'] != null) {
      return const ['查看任务进度', '解析一个 PDF 为 Markdown', '把这篇文档转成 Word'];
    }
    return const ['把 Vue 文档爬下来转 Word', '解析一个 PDF 为 Markdown'];
  }

  void _onFollowUp(String value) {
    if (value == '查看任务进度') {
      onViewHistory();
      return;
    }
    onSendText(value);
  }
}

// ---- Markdown 回复体（L19）：正文 token 化 + 代码块高亮主题随昼夜档 ----

/// 星伴回复 Markdown 渲染（公开以便金测/单测直测渲染路径；
/// 配置与抽屉消息行同源）。
class AiMarkdownReply extends StatelessWidget {
  const AiMarkdownReply({required this.text, required this.palette, super.key});

  final String text;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    final dark = AstroPaletteScope.darkProgressOf(context) >= 0.5;
    final bodyStyle = TextStyle(
      fontSize: AstroType.body.size,
      height: AstroType.body.height / AstroType.body.size,
      color: palette.ink900,
    );
    return MarkdownWidget(
      data: text,
      // 嵌入抽屉列表：自收缩、不滚动（滚动交给抽屉 ListView）
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.zero,
      config: MarkdownConfig(configs: [
        PConfig(textStyle: bodyStyle),
        H1Config(
            style: TextStyle(
                fontSize: AstroType.title.size,
                height: AstroType.title.height / AstroType.title.size,
                fontWeight: FontWeight.w600,
                color: palette.ink900)),
        H2Config(
            style: TextStyle(
                fontSize: AstroType.titleSm.size,
                height: AstroType.titleSm.height / AstroType.titleSm.size,
                fontWeight: FontWeight.w600,
                color: palette.ink900)),
        H3Config(
            style: TextStyle(
                fontSize: AstroType.body.size,
                fontWeight: FontWeight.w600,
                color: palette.ink900)),
        CodeConfig(
          style: TextStyle(
            fontFamily: AstroType.monoFamily,
            fontSize: AstroType.bodySm.size,
            color: palette.nebulaText,
            backgroundColor: palette.aiContainerBg,
          ),
        ),
        PreConfig(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.symmetric(vertical: 6),
          decoration: BoxDecoration(
            color: palette.sunken,
            borderRadius: BorderRadius.circular(AstroRadius.sm),
          ),
          textStyle: TextStyle(
            fontFamily: AstroType.monoFamily,
            fontSize: AstroType.bodySm.size,
            height: 1.5,
            color: palette.ink900,
          ),
          // 高亮主题映射（包内主题表，本库不散落色值）：昼 github / 夜 atom-one-dark
          theme: dark ? atomOneDarkTheme : githubTheme,
          styleNotMatched: TextStyle(
            fontFamily: AstroType.monoFamily,
            fontSize: AstroType.bodySm.size,
            color: palette.ink900,
          ),
        ),
        BlockquoteConfig(
          textColor: palette.ink600,
          sideColor: palette.stroke,
        ),
      ]),
    );
  }
}

/// 消息操作行按钮（L19：18dp lucide 线性图标，ink-400 hover 升 ink-900）。
class _MessageAction extends StatefulWidget {
  const _MessageAction({
    required this.tooltip,
    required this.icon,
    required this.palette,
    required this.onTap,
  });

  final String tooltip;
  final IconData icon;
  final AstroPalette palette;
  final VoidCallback onTap;

  @override
  State<_MessageAction> createState() => _MessageActionState();
}

class _MessageActionState extends State<_MessageAction> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: widget.tooltip,
      waitDuration: const Duration(milliseconds: 300),
      child: InkWell(
        onTap: widget.onTap,
        onHover: (hover) => setState(() => _hover = hover),
        borderRadius: BorderRadius.circular(AstroRadius.sm),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Icon(
            widget.icon,
            size: 18, // L19 契约：18dp 线性图标
            color: _hover ? widget.palette.ink900 : widget.palette.ink400,
          ),
        ),
      ),
    );
  }
}

/// 追问 chips（L19）：错峰 60ms/枚 上浮淡入（#13 同族，更密节奏）；
/// reduced-motion 瞬时到位。
class _FollowUpChips extends StatelessWidget {
  const _FollowUpChips({
    required this.palette,
    required this.suggestions,
    required this.onSelected,
  });

  final AstroPalette palette;
  final List<String> suggestions;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final reduced = MediaQuery.disableAnimationsOf(context);
    return Wrap(
      spacing: AstroSpace.gap,
      runSpacing: AstroSpace.gap,
      children: [
        for (var i = 0; i < suggestions.length; i++)
          _ChipStagger(
            delay: reduced
                ? Duration.zero
                : Duration(milliseconds: 60 * i), // L19 契约：stagger 60ms
            child: ActionChip(
              backgroundColor: palette.container.withValues(alpha: 0.6),
              side: BorderSide(color: palette.stroke),
              label: Text(
                suggestions[i],
                style: TextStyle(
                  fontSize: AstroType.caption.size,
                  color: palette.ink600,
                ),
              ),
              onPressed: () => onSelected(suggestions[i]),
            ),
          ),
      ],
    );
  }
}

/// 单枚 chip 错峰入场：translateY 8→0 + fade，200ms（交互反馈红线内）。
class _ChipStagger extends StatefulWidget {
  const _ChipStagger({required this.delay, required this.child});

  final Duration delay;
  final Widget child;

  @override
  State<_ChipStagger> createState() => _ChipStaggerState();
}

class _ChipStaggerState extends State<_ChipStagger>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 200),
  );

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(widget.delay, () {
      if (mounted) _controller.forward();
    });
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
          child: Transform.translate(offset: Offset(0, 8 * (1 - t)), child: child),
        );
      },
      child: widget.child,
    );
  }
}

// ---- 思考三点错相（#6：alpha 0.3→1 循环 1.2s，错相 0.2s）----

class _ThinkingDots extends StatefulWidget {
  const _ThinkingDots({required this.palette});

  final AstroPalette palette;

  @override
  State<_ThinkingDots> createState() => _ThinkingDotsState();
}

class _ThinkingDotsState extends State<_ThinkingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  final _startedAt = DateTime.now();

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    if (!MediaQuery.disableAnimationsOf(context)) {
      _controller.repeat();
    } else {
      _controller.value = 0.5; // reduced-motion：静态中值帧
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
      builder: (context, _) {
        final elapsed = DateTime.now().difference(_startedAt).inSeconds;
        return Row(
          children: [
            Text(AstroIcons.aiThinking,
                style: TextStyle(color: widget.palette.nebula, fontSize: AstroType.body.size)),
            const SizedBox(width: 8),
            for (var i = 0; i < 3; i++)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Opacity(
                  // 三点错相 0.2s：alpha 0.3→1 循环（1.2s 周期）
                  opacity: 0.3 + 0.7 * _wave(_controller.value, i),
                  child: Text(
                    '·',
                    style: TextStyle(
                      color: widget.palette.nebula,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            const SizedBox(width: 10),
            Text(
              '思忖中 $elapsed s',
              style: TextStyle(
                fontSize: AstroType.caption.size,
                fontFeatures: const [FontFeature.tabularFigures()],
                color: widget.palette.ink400,
              ),
            ),
          ],
        );
      },
    );
  }

  /// 错相波形：index 每点滞后 0.2s（1.2s 周期的 1/6 相位）。
  double _wave(double t, int index) {
    final phase = (t - index * (0.2 / 1.2)) % 1.0;
    final s = phase < 0 ? phase + 1 : phase;
    return 0.5 + 0.5 * math.sin(2 * math.pi * s - math.pi / 2);
  }
}

// ---- 底部输入条（sunken 井 + Ctrl+Enter 发送）----

class _ComposerBar extends StatelessWidget {
  const _ComposerBar({
    required this.palette,
    required this.composer,
    required this.onSend,
  });

  final AstroPalette palette;
  final TextEditingController composer;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Actions(
      actions: {
        SendIntent: CallbackAction<SendIntent>(
          onInvoke: (_) {
            onSend();
            return null;
          },
        ),
      },
      child: Padding(
        padding: const EdgeInsets.all(AstroSpace.card),
        child: Row(
          children: [
            Expanded(
              child: Container(
                height: 44,
                decoration: BoxDecoration(
                  color: palette.sunken,
                  borderRadius: BorderRadius.circular(AstroRadius.pill),
                  border: Border.all(color: palette.stroke),
                ),
                child: Padding(
                  padding: const EdgeInsets.only(left: 14),
                  child: TextField(
                    controller: composer,
                    style: TextStyle(
                        fontSize: AstroType.body.size, color: palette.ink900),
                    cursorColor: palette.aurora,
                    decoration: InputDecoration.collapsed(
                      hintText: '输入指令或问题…（Ctrl+Enter 发送）',
                      hintStyle: TextStyle(
                          fontSize: AstroType.bodySm.size,
                          color: palette.ink400),
                    ),
                    onSubmitted: (_) => onSend(),
                  ),
                ),
              ),
            ),
            const SizedBox(width: AstroSpace.gap),
            SizedBox(
              width: 44,
              height: 44,
              child: IconButton.filled(
                tooltip: '发送（Ctrl+Enter）',
                onPressed: onSend,
                style: IconButton.styleFrom(backgroundColor: palette.nebula),
                icon: Icon(Icons.auto_awesome, size: 18, color: palette.onNebula),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
