import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';

import '../../core/design/design.dart';

/// 液态指示胶囊组（§1.8 #3：胶囊背景拉长→收缩→回弹 spring(300, 0.6)）。
/// 任务页类型切换 / 监控 range 切换共用；指示胶囊跨项滑移由
/// 前后选中项矩形 lerp 驱动（矩形经 GlobalKey 实测，禁估算宽度）。
class LiquidChipItem {
  const LiquidChipItem({
    required this.key,
    required this.glyph,
    required this.label,
    this.disabled = false,
    this.disabledNote,
  });

  final String key;
  final String glyph;
  final String label;

  /// 禁用态（如 spider_table「开发中」）。
  final bool disabled;
  final String? disabledNote;
}

class LiquidChipRow extends StatefulWidget {
  const LiquidChipRow({
    required this.items,
    required this.selected,
    required this.onSelect,
    this.wrap = true,
    super.key,
  });

  final List<LiquidChipItem> items;
  final String selected;
  final ValueChanged<String> onSelect;

  /// 超宽容器是否换行（任务页 8 类型换行；监控 range 4 段单行）。
  final bool wrap;

  @override
  State<LiquidChipRow> createState() => _LiquidChipRowState();
}

class _LiquidChipRowState extends State<LiquidChipRow>
    with SingleTickerProviderStateMixin {
  final _itemKeys = <String, GlobalKey>{};
  final _rowKey = GlobalKey();
  Rect? _fromRect;
  Rect? _toRect;
  late final AnimationController _slide = AnimationController(vsync: this);
  String? _lastSelected;

  @override
  void dispose() {
    _slide.dispose();
    super.dispose();
  }

  GlobalKey _keyOf(String key) => _itemKeys.putIfAbsent(key, GlobalKey.new);

  Rect? _rectOf(String key) {
    final ctx = _keyOf(key).currentContext;
    final box = ctx?.findRenderObject() as RenderBox?;
    final rowBox = _rowKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null || rowBox == null || !box.attached) return null;
    return box.localToGlobal(Offset.zero) -
        rowBox.localToGlobal(Offset.zero) & box.size;
  }

  /// 是否有待测量的选中变化（稳态 false——禁 postframe→setState 死循环）。
  bool get _measurePending => _lastSelected != widget.selected;

  void _scheduleSlide() {
    if (_lastSelected == widget.selected) return;
    final from = _rectOf(_lastSelected ?? widget.selected) ?? _rectOf(widget.selected);
    final to = _rectOf(widget.selected);
    _lastSelected = widget.selected;
    if (from == null || to == null) {
      _fromRect = null;
      return;
    }
    _fromRect = from;
    _toRect = to;
    // spring(300, 0.6)：ζ0.6 → damping = 0.6*2*sqrt(300)（§1.4 #3，禁自造曲线）
    const stiffness = 300.0;
    final damping = 0.6 * 2 * math.sqrt(stiffness);
    _slide.animateWith(
      SpringSimulation(
        SpringDescription(mass: 1, stiffness: stiffness, damping: damping),
        0,
        1,
        0,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = AstroPaletteScope.of(context);
    // 布局后实测矩形 → 计算滑移（首帧选中项只做淡入，无滑移）；
    // 仅在选中变化后的那一帧 setState，稳态零重排
    if (_measurePending) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _measurePending) setState(_scheduleSlide);
      });
    }
    final children = <Widget>[
      for (final item in widget.items)
        _Chip(
          itemKey: _keyOf(item.key),
          item: item,
          selected: item.key == widget.selected,
          palette: palette,
          onSelect: item.disabled ? null : () => widget.onSelect(item.key),
        ),
    ];

    Widget content;
    if (widget.wrap) {
      content = Wrap(spacing: 8, runSpacing: 8, children: children);
    } else {
      content = Row(mainAxisSize: MainAxisSize.min, children: children);
    }

    return KeyedSubtree(
      key: _rowKey,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          // 指示胶囊层（chipsSelectedBg：aurora@12% 合成 token）
          if (_fromRect != null && _toRect != null)
            AnimatedBuilder(
              animation: _slide,
              builder: (context, _) {
                final t = Curves.linear.transform(_slide.value);
                final rect = Rect.lerp(_fromRect, _toRect, t)!;
                return Positioned(
                  left: rect.left,
                  top: rect.top,
                  width: rect.width,
                  height: rect.height,
                  child: Container(
                    decoration: BoxDecoration(
                      color: palette.chipsSelectedBg,
                      borderRadius: BorderRadius.circular(AstroRadius.pill),
                    ),
                  ),
                );
              },
            ),
          Padding(
            // 指示胶囊为背景层，chips 内容本体带 padding 避免叠字
            padding: const EdgeInsets.all(2),
            child: content,
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatefulWidget {
  const _Chip({
    required this.itemKey,
    required this.item,
    required this.selected,
    required this.palette,
    this.onSelect,
  });

  final GlobalKey itemKey;
  final LiquidChipItem item;
  final bool selected;
  final AstroPalette palette;
  final VoidCallback? onSelect;

  @override
  State<_Chip> createState() => _ChipState();
}

class _ChipState extends State<_Chip> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final palette = widget.palette;
    final enabled = widget.onSelect != null;
    final color = !enabled
        ? palette.ink400
        : widget.selected
            // 昼档文本走 auroraText（星空设计系统规格 §一）
            ? palette.auroraText
            : _hover
                ? palette.ink900
                : palette.ink600;
    return KeyedSubtree(
      key: widget.itemKey,
      child: Tooltip(
        message: widget.item.disabledNote ?? '',
        child: MouseRegion(
          cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
          onEnter: (_) => setState(() => _hover = true),
          onExit: (_) => setState(() => _hover = false),
          child: GestureDetector(
            onTap: widget.onSelect,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: AstroMotion.tweenColorMs),
              curve: AstroMotion.tweenEasing,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AstroRadius.pill),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    widget.item.glyph,
                    style: TextStyle(fontSize: 13, color: color),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    widget.item.label,
                    style: TextStyle(
                      fontSize: AstroType.bodySm.size,
                      fontWeight:
                          widget.selected ? FontWeight.w600 : FontWeight.w400,
                      color: color,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
