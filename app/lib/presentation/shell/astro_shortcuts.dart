import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// 壳层键盘导航（§5.1 键盘表；UX 评审 P0-3——语义与 TUI 同名映射）。
/// MF5 全集落位：Ctrl+1~5 切页（IA 8→5）/ Ctrl+K 命令面板 /
/// Ctrl+` 日志面板 / Ctrl+Shift+A 星伴抽屉 / Ctrl+Enter 发送 /
/// Ctrl+I 聚焦输入条 / F5 刷新当前页 / Esc 逐层退出。
class OpenAiDrawerIntent extends Intent {
  const OpenAiDrawerIntent();
}

class NavBranchIntent extends Intent {
  const NavBranchIntent(this.index);

  final int index;
}

class SendIntent extends Intent {
  const SendIntent();
}

class FocusComposerIntent extends Intent {
  const FocusComposerIntent();
}

class RefreshIntent extends Intent {
  const RefreshIntent();
}

class EscapeLayerIntent extends Intent {
  const EscapeLayerIntent();
}

/// 命令面板（Ctrl+K；TUI `/` 同名映射）。
class OpenPaletteIntent extends Intent {
  const OpenPaletteIntent();
}

/// 日志面板（Ctrl+`；TUI Ctrl+` 同名映射）。
class OpenLogPanelIntent extends Intent {
  const OpenLogPanelIntent();
}

/// 壳层快捷键表（Ctrl+Shift+A 真实 Shortcuts 绑定——修复旧「仅 tooltip」假绑定）。
Map<ShortcutActivator, Intent> astroShortcuts() => {
      // 星伴 AI 抽屉（TUI A 键同名映射）
      const SingleActivator(LogicalKeyboardKey.keyA,
          control: true, shift: true): const OpenAiDrawerIntent(),
      // 切页 Ctrl+1~5（IA 8→5：首页/任务/流水线/历史/设置）
      for (final (i, key) in const [
        (0, LogicalKeyboardKey.digit1),
        (1, LogicalKeyboardKey.digit2),
        (2, LogicalKeyboardKey.digit3),
        (3, LogicalKeyboardKey.digit4),
        (4, LogicalKeyboardKey.digit5),
      ])
        SingleActivator(key, control: true): NavBranchIntent(i),
      // 命令面板 / 日志面板
      const SingleActivator(LogicalKeyboardKey.keyK, control: true):
          const OpenPaletteIntent(),
      const SingleActivator(LogicalKeyboardKey.backquote, control: true):
          const OpenLogPanelIntent(),
      // 发送 / 全局聚焦输入条 / 刷新
      const SingleActivator(LogicalKeyboardKey.enter, control: true):
          const SendIntent(),
      const SingleActivator(LogicalKeyboardKey.numpadEnter, control: true):
          const SendIntent(),
      const SingleActivator(LogicalKeyboardKey.keyI, control: true):
          const FocusComposerIntent(),
      const SingleActivator(LogicalKeyboardKey.f5): const RefreshIntent(),
      // 逐层退出：弹层→面板→输入条失焦→无操作（抽屉/弹窗自带 Esc，
      // 这里兜底处理剩余层的失焦）
      const SingleActivator(LogicalKeyboardKey.escape): const EscapeLayerIntent(),
    };
