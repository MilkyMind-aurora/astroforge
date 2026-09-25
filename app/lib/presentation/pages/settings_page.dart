import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';
import '../../data/api_client/dio_client.dart';

/// 设置页（Kimi iOS 分组内嵌卡【K4 3.4】，方案 §5.7）：
/// 分组组卡（container 底 R16，组间 24）——「外观」（主题三选触点圆形扩散
/// #2 + 星野/星仔开关）、「引擎」（只读：config-summary）、「服务」（地址 +
/// Token 重置=危险行 nova 字+滑动确认【D24 G7】）、「路径」（config-summary
/// 只读行）、「关于」。行=图标 20 ink-600+题 15 ink-900+值 13 ink-400+chevron。
class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  Map<String, dynamic>? _summary;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
    ref.listenManual(refreshEventsProvider, (_, _) => _refresh());
  }

  Future<void> _refresh() async {
    final api = ref.read(apiClientProvider);
    try {
      final summary = await api.configSummary();
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    final summary = _summary;
    return ListView(
      padding: const EdgeInsets.all(AstroSpace.section),
      children: [
        Text('设置',
            style: TextStyle(
                fontSize: AstroType.h1.size,
                fontWeight: AstroType.h1.weight,
                color: palette.ink900)),
        const SizedBox(height: 4),
        Text('外观即时生效 · 服务端设置双端同源（app_settings 白名单）',
            style: TextStyle(
                fontSize: AstroType.bodySm.size, color: palette.ink600)),
        const SizedBox(height: AstroSpace.sectionLg),
        if (_error != null) ...[
          Text('config-summary 加载失败：$_error',
              style: TextStyle(
                  fontSize: AstroType.bodySm.size, color: palette.nova)),
          const SizedBox(height: AstroSpace.section),
        ],

        // ---- 外观（主题三选即选即生效 + #2 触点圆形扩散）----
        _GroupCard(
          title: '外观',
          palette: palette,
          children: [
            _ThemeRow(palette: palette),
            _SwitchRow(
              icon: LucideIcons.sparkles,
              title: '星野背景',
              subtitle: '壳层星点缓漂与流星（双端同源 appearance.starfield）',
              value: ref.watch(appearanceProvider).starfield,
              onChanged: (v) =>
                  ref.read(appearanceProvider.notifier).setStarfield(v),
              palette: palette,
            ),
            _SwitchRow(
              icon: LucideIcons.orbit,
              title: '星仔',
              subtitle: '吉祥物常驻位（双端同源 appearance.mascot）',
              value: ref.watch(appearanceProvider).mascot,
              onChanged: (v) =>
                  ref.read(appearanceProvider.notifier).setMascot(v),
              palette: palette,
            ),
          ],
        ),

        // ---- 引擎（只读：服务端 config-summary）----
        _GroupCard(
          title: '引擎',
          palette: palette,
          children: [
            _InfoRow(
              icon: LucideIcons.cpu,
              title: '默认模型',
              value: '${_aiField('default_model') ?? '—'}',
              palette: palette,
            ),
            _InfoRow(
              icon: LucideIcons.timer,
              title: '闲置卸载时长',
              value: '${_aiField('idle_timeout') ?? '—'}',
              palette: palette,
            ),
          ],
        ),

        // ---- 服务（地址 + 危险行）----
        _GroupCard(
          title: '服务',
          palette: palette,
          children: [
            _InfoRow(
              icon: LucideIcons.server,
              title: '服务地址',
              value: _serviceAddr(),
              palette: palette,
            ),
            _InfoRow(
              icon: LucideIcons.database,
              title: '数据库',
              value: _dbAddr(),
              palette: palette,
            ),
            // 危险行：nova 字 + 滑动确认（清凭据语义，敏感操作替代二次弹窗）
            _SlideConfirmRow(
              icon: LucideIcons.keyRound,
              title: '重置服务 Token',
              subtitle: '旧 token 立即失效，客户端自动重新读取',
              palette: palette,
              onConfirmed: _resetToken,
            ),
          ],
        ),

        // ---- 路径（config-summary 只读行）----
        _GroupCard(
          title: '路径',
          palette: palette,
          children: [
            for (final entry in _pathRows(summary))
              _InfoRow(
                icon: LucideIcons.folder,
                title: entry.$1,
                value: entry.$2,
                palette: palette,
              ),
          ],
        ),

        // ---- 关于 ----
        _GroupCard(
          title: '关于',
          palette: palette,
          children: [
            _InfoRow(
              icon: LucideIcons.info,
              title: '版本代号',
              value: '0.1.0 · Sidereal Core',
              palette: palette,
            ),
            _InfoRow(
              icon: LucideIcons.scale,
              title: '开源许可',
              value: 'LICENSE（仓库根目录）',
              palette: palette,
            ),
            _InfoRow(
              icon: LucideIcons.scrollText,
              title: '服务日志',
              value: 'data/logs/service.log',
              palette: palette,
            ),
          ],
        ),
        const SizedBox(height: AstroSpace.section),
        Align(
          child: TextButton(
            onPressed: () => context.go('/home'),
            child: Text('返回首页（Esc 逐层退出同样生效）',
                style: TextStyle(
                    fontSize: AstroType.caption.size, color: palette.ink400)),
          ),
        ),
      ],
    );
  }

  dynamic _aiField(String key) =>
      (_summary?['ai'] as Map?)?.cast<String, dynamic>()[key];

  String _serviceAddr() {
    final service = (_summary?['service'] as Map?)?.cast<String, dynamic>();
    if (service == null) return '—';
    return '${service['host']}:${service['port']}';
  }

  String _dbAddr() {
    final db = (_summary?['database'] as Map?)?.cast<String, dynamic>();
    if (db == null) return '—';
    return '${db['host']}:${db['port']} · ${db['db_name']}';
  }

  List<(String, String)> _pathRows(Map<String, dynamic>? summary) {
    if (summary == null) return [];
    final md2docx = (summary['md2docx'] as Map?)?.cast<String, dynamic>();
    final monitor = (summary['monitor'] as Map?)?.cast<String, dynamic>();
    final system = (summary['system'] as Map?)?.cast<String, dynamic>();
    return [
      ('默认 DOCX 模板', '${md2docx?['default_template'] ?? '—'}'),
      ('内存预警/红线 (GB)',
          '${monitor?['memory_warning_gb'] ?? '—'} / ${monitor?['memory_critical_gb'] ?? '—'}'),
      ('任务并发', '${system?['task_concurrency'] ?? '—'}'),
    ];
  }

  Future<void> _resetToken() async {
    final api = ref.read(apiClientProvider);
    try {
      await api.resetToken();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Token 已重置（客户端下次请求自动重新读取）')),
      );
    } on ApiError catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${AstroIcons.statusError} [${e.code}] ${e.message}')),
      );
    }
  }
}

// ---- 分组组卡（container 底 R16，组间 24）----

class _GroupCard extends StatelessWidget {
  const _GroupCard({
    required this.title,
    required this.palette,
    required this.children,
  });

  final String title;
  final AstroPalette palette;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AstroSpace.section),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  fontSize: AstroType.titleSm.size,
                  fontWeight: FontWeight.w600,
                  color: palette.ink600)),
          const SizedBox(height: AstroSpace.gap),
          FocusTraversalGroup(
            child: Container(
              padding: const EdgeInsets.all(AstroSpace.card),
              decoration: BoxDecoration(
                color: palette.container,
                borderRadius: BorderRadius.circular(AstroRadius.md),
              ),
              child: Column(
                children: [
                  for (var i = 0; i < children.length; i++) ...[
                    if (i > 0) const SizedBox(height: AstroSpace.gap),
                    children[i],
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---- 行基座：图标 20 + 题 15 + 值/副题 13 ----

class _RowBase extends StatelessWidget {
  const _RowBase({
    required this.icon,
    required this.title,
    required this.palette,
    this.subtitle,
    this.trailing,
  });

  final IconData icon;
  final String title;
  final AstroPalette palette;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final sub = subtitle;
    return Row(
      children: [
        Icon(icon, size: 20, color: palette.ink600),
        const SizedBox(width: AstroSpace.gapLg),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: TextStyle(
                      fontSize: AstroType.titleSm.size, color: palette.ink900)),
              if (sub != null && sub.isNotEmpty) ...[
                const SizedBox(height: 1),
                Text(sub,
                    style: TextStyle(
                        fontSize: AstroType.caption.size,
                        color: palette.ink400)),
              ],
            ],
          ),
        ),
        ?trailing,
      ],
    );
  }
}

/// 只读行（值 ink-400）。
class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.title,
    required this.value,
    required this.palette,
  });

  final IconData icon;
  final String title;
  final String value;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: _RowBase(
        icon: icon,
        title: title,
        palette: palette,
        subtitle: value,
      ),
    );
  }
}

/// 开关行（iOS 风格内嵌 Switch；aurora 主题由 ThemeData 接管）。
class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
    required this.palette,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  final AstroPalette palette;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: _RowBase(
        icon: icon,
        title: title,
        subtitle: subtitle,
        palette: palette,
        trailing: Switch(value: value, onChanged: onChanged),
      ),
    );
  }
}

/// 主题三选行（跟随系统/夜/昼；即选即生效 + #2 触点圆形扩散）。
class _ThemeRow extends ConsumerWidget {
  const _ThemeRow({required this.palette});

  final AstroPalette palette;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(astroThemeModeProvider);
    final options = <(ThemeMode, String, IconData)>[
      (ThemeMode.system, '跟随系统', LucideIcons.sunMoon),
      (ThemeMode.dark, '夜', LucideIcons.moon),
      (ThemeMode.light, '昼', LucideIcons.sun),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: _RowBase(
        icon: LucideIcons.palette,
        title: '主题',
        subtitle: '点击即生效（250ms 全色板过渡 · 触点圆形扩散）',
        palette: palette,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final (value, label, icon) in options)
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: _ThemeChip(
                  label: label,
                  icon: icon,
                  selected: value == mode,
                  palette: palette,
                  onTap: () {
                    // #2 触点圆形扩散：从点击位置 reveal
                    AstroThemeReveal.change(
                      context,
                      // ThemeMode → AstroThemeMode 同名映射
                      switch (value) {
                        ThemeMode.dark => AstroThemeMode.dark,
                        ThemeMode.light => AstroThemeMode.light,
                        ThemeMode.system => AstroThemeMode.system,
                      },
                      origin: _centerOf(context),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _ThemeChip extends StatelessWidget {
  const _ThemeChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.palette,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final AstroPalette palette;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AstroRadius.pill),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? palette.chipsSelectedBg : palette.bg.withValues(alpha: 0),
          borderRadius: BorderRadius.circular(AstroRadius.pill),
          border: Border.all(
            color: selected ? palette.aurora : palette.stroke,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon,
                size: 14,
                color: selected ? palette.auroraText : palette.ink600),
            const SizedBox(width: 4),
            Text(label,
                style: TextStyle(
                    fontSize: AstroType.label.size,
                    color: selected ? palette.auroraText : palette.ink600)),
          ],
        ),
      ),
    );
  }
}

/// 危险行滑动确认（【D24 G7】：滑过 80% 触发，不足回弹；敏感操作替代二次弹窗）。
class _SlideConfirmRow extends StatefulWidget {
  const _SlideConfirmRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.palette,
    required this.onConfirmed,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final AstroPalette palette;
  final Future<void> Function() onConfirmed;

  @override
  State<_SlideConfirmRow> createState() => _SlideConfirmRowState();
}

class _SlideConfirmRowState extends State<_SlideConfirmRow>
    with SingleTickerProviderStateMixin {
  static const _trackWidth = 196.0;
  static const _knobSize = 32.0;

  double _dragExtent = 0;
  bool _firing = false;
  late final AnimationController _snapBack = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: AstroMotion.tweenMoveMs),
  );

  @override
  void dispose() {
    _snapBack.dispose();
    super.dispose();
  }

  void _onDragUpdate(DragUpdateDetails details) {
    if (_firing) return;
    setState(() {
      _dragExtent =
          (_dragExtent + details.delta.dx).clamp(0.0, _trackWidth - _knobSize);
    });
  }

  void _onDragEnd(DragEndDetails details) {
    final ratio = _dragExtent / (_trackWidth - _knobSize);
    if (ratio >= AstroInteraction.swipeConfirmRatio) {
      _fire();
    } else {
      // 不足回弹（TWEEN_MOVE）
      _snapBack.forward(from: 0);
    }
  }

  Future<void> _fire() async {
    if (_firing) return;
    setState(() => _firing = true);
    try {
      await widget.onConfirmed();
    } finally {
      if (mounted) {
        setState(() {
          _firing = false;
          _dragExtent = 0;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    final done = _dragExtent >= (_trackWidth - _knobSize) - 0.5;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: _RowBase(
        icon: widget.icon,
        title: widget.title,
        subtitle: widget.subtitle,
        palette: palette,
        trailing: GestureDetector(
          onHorizontalDragUpdate: _onDragUpdate,
          onHorizontalDragEnd: _onDragEnd,
          child: AnimatedBuilder(
            animation: _snapBack,
            builder: (context, _) {
              final extent = _snapBack.isAnimating
                  ? _dragExtent * (1 - Curves.easeOutCubic.transform(_snapBack.value))
                  : _dragExtent;
              return Container(
                width: _trackWidth,
                height: _knobSize + 8,
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: done ? palette.nova.withValues(alpha: 0.16) : palette.card,
                  borderRadius: BorderRadius.circular(AstroRadius.pill),
                  border: Border.all(
                    color: done ? palette.nova : palette.stroke,
                    width: done ? 1.5 : 1,
                  ),
                ),
                child: Stack(
                  alignment: Alignment.centerLeft,
                  children: [
                    Center(
                      child: Text(
                        extent > (_trackWidth - _knobSize) * 0.5
                            ? '松手确认'
                            : '滑动确认重置',
                        style: TextStyle(
                          fontSize: AstroType.label.size,
                          color: done ? palette.nova : palette.ink400,
                        ),
                      ),
                    ),
                    Positioned(
                      left: extent,
                      child: Container(
                        width: _knobSize,
                        height: _knobSize,
                        decoration: BoxDecoration(
                          color: done ? palette.nova : palette.ink600,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          LucideIcons.chevronRight,
                          size: 16,
                          color: palette.onNova,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// 触点中心全局坐标（#2 reveal 起点）。
Offset? _centerOf(BuildContext context) {
  final box = context.findRenderObject();
  if (box is! RenderBox || !box.hasSize) return null;
  return box.localToGlobal(box.size.center(Offset.zero));
}
