import 'package:flutter/material.dart';

import '../../core/design/design.dart';

/// 模型两档清单（§5.6：与 Kimi 模型弹层完全同构；键与服务核心
/// routes_ai.KNOWN_MODELS 白名单同源——未知键服务端拒绝透传）。
const astroModels = <String, (String, String)>{
  'qwen2b': ('Qwen3.8-2B', '常驻 · 日常指令'),
  'ornith9b': ('Ornith-9B', '按需 · 复杂拆解 · ≈5.6GB'),
};

String modelDisplayName(String key) => astroModels[key]?.$1 ?? key;

/// 模型选择弹层（星空设计系统规格 §三.8）：w300 R16 cardRaised 贴触发位
/// 生长 280ms + scrim bg@70% + 行 h56（星符+名+定位副题+✓ aurora）；
/// 引擎忙时行禁用「引擎忙…」。
Future<void> showModelSheet(
  BuildContext context, {
  required String currentModel,
  required bool busy,
  required ValueChanged<String> onSelect,
}) {
  return showDialog<void>(
    context: context,
    barrierColor: AstroPaletteScope.of(context).bg.withValues(alpha: 0.70),
    barrierLabel: '模型选择',
    builder: (dialogContext) {
      final palette = AstroPaletteScope.of(dialogContext);
      return Align(
        alignment: Alignment.topRight,
        child: Padding(
          // 贴触发位（右上模型胶囊下方）生长
          padding: const EdgeInsets.only(top: 64, right: 24),
          child: _ModelSheet(
            palette: palette,
            currentModel: currentModel,
            busy: busy,
            onSelect: (key) {
              Navigator.of(dialogContext).pop();
              onSelect(key);
            },
          ),
        ),
      );
    },
  );
}

class _ModelSheet extends StatefulWidget {
  const _ModelSheet({
    required this.palette,
    required this.currentModel,
    required this.busy,
    required this.onSelect,
  });

  final AstroPalette palette;
  final String currentModel;
  final bool busy;
  final ValueChanged<String> onSelect;

  @override
  State<_ModelSheet> createState() => _ModelSheetState();
}

class _ModelSheetState extends State<_ModelSheet>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  // 拖回双判（§1.7）：位移>96dp 或 速度>1000dp/s 满足其一即关
  double _dragDy = 0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 280),
    );
  }

  bool _reduced = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = MediaQuery.disableAnimationsOf(context);
    if (_reduced) {
      _controller.value = 1.0;
    } else if (!_controller.isAnimating) {
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
    final palette = widget.palette;
    return GestureDetector(
      onVerticalDragUpdate: (details) =>
          setState(() => _dragDy += details.delta.dy),
      onVerticalDragEnd: (details) {
        final velocity = details.primaryVelocity ?? 0;
        if (_dragDy > AstroInteraction.sheetDismissDistanceDp ||
            velocity > AstroInteraction.sheetDismissVelocityDps) {
          Navigator.of(context).pop();
        } else {
          setState(() => _dragDy = 0);
        }
      },
      child: ScaleTransition(
        scale: CurvedAnimation(
          parent: _controller,
          curve: Curves.easeOutBack, // 生长式（0.85→1.02→1 的简化同族）
        ).drive(Tween(begin: 0.85, end: 1.0)),
        alignment: Alignment.topRight,
        child: Material(
          color: palette.cardRaised,
          borderRadius: BorderRadius.circular(AstroRadius.md),
          child: Container(
            width: 300,
            padding: const EdgeInsets.symmetric(vertical: 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AstroRadius.md),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final entry in astroModels.entries)
                  _ModelRow(
                    palette: palette,
                    modelKey: entry.key,
                    displayName: entry.value.$1,
                    subtitle: entry.value.$2,
                    selected: entry.key == widget.currentModel,
                    busy: widget.busy,
                    onSelect: () => widget.onSelect(entry.key),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ModelRow extends StatelessWidget {
  const _ModelRow({
    required this.palette,
    required this.modelKey,
    required this.displayName,
    required this.subtitle,
    required this.selected,
    required this.busy,
    required this.onSelect,
  });

  final AstroPalette palette;
  final String modelKey;
  final String displayName;
  final String subtitle;
  final bool selected;
  final bool busy;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: busy ? null : onSelect,
      child: Container(
        height: 56, // 行 h56（规格 §三.8）
        padding: const EdgeInsets.symmetric(horizontal: AstroSpace.card),
        child: Row(
          children: [
            Text(
              AstroIcons.aiIdle,
              style: TextStyle(
                color: selected ? palette.nebula : palette.ink600,
                fontSize: 15,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    displayName,
                    style: TextStyle(
                      fontSize: AstroType.titleSm.size,
                      fontWeight: FontWeight.w500,
                      color: palette.ink900,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: AstroType.caption.size,
                      color: palette.ink400,
                    ),
                  ),
                ],
              ),
            ),
            if (busy)
              Text(
                '引擎忙…',
                style: TextStyle(
                    fontSize: AstroType.caption.size, color: palette.ink400),
              )
            else if (selected)
              Text(
                AstroIcons.taskSuccess,
                style: TextStyle(color: palette.aurora, fontSize: 15),
              ),
          ],
        ),
      ),
    );
  }
}
