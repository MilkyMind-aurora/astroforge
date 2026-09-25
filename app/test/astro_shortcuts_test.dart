// 壳层键盘导航测试（UX P0-3）：Ctrl+Shift+A 星伴抽屉的真实 Shortcuts/Actions
// 绑定（修复旧「仅 tooltip 无绑定」）、Ctrl+数字切页意图分发。
import 'package:astroforge/presentation/shell/astro_shortcuts.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Ctrl+Shift+A 触发 OpenAiDrawerIntent（bug②修复断言）', (tester) async {
    var invoked = 0;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            OpenAiDrawerIntent: CallbackAction<OpenAiDrawerIntent>(
              onInvoke: (_) {
                invoked++;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.keyA);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.keyA);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(invoked, 1);
  });

  testWidgets('Ctrl+2 触发切页意图（index=1）', (tester) async {
    var lastIndex = -1;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            NavBranchIntent: CallbackAction<NavBranchIntent>(
              onInvoke: (intent) {
                lastIndex = intent.index;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.digit2);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.digit2);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(lastIndex, 1);
  });

  testWidgets('无修饰的 A 不触发星伴抽屉（防误触）', (tester) async {
    var invoked = 0;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            OpenAiDrawerIntent: CallbackAction<OpenAiDrawerIntent>(
              onInvoke: (_) {
                invoked++;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.keyA);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.keyA);
    await tester.pump();

    expect(invoked, 0);
  });

  testWidgets('Ctrl+6 不再切页（IA 8→5 后仅 Ctrl+1~5）', (tester) async {
    var lastIndex = -1;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            NavBranchIntent: CallbackAction<NavBranchIntent>(
              onInvoke: (intent) {
                lastIndex = intent.index;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.digit6);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.digit6);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(lastIndex, -1);
  });

  testWidgets('Ctrl+K 触发命令面板意图', (tester) async {
    var opened = 0;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            OpenPaletteIntent: CallbackAction<OpenPaletteIntent>(
              onInvoke: (_) {
                opened++;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.keyK);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.keyK);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(opened, 1);
  });

  testWidgets('Ctrl+` 触发日志面板意图', (tester) async {
    var opened = 0;
    await tester.pumpWidget(MaterialApp(
      home: Shortcuts(
        shortcuts: astroShortcuts(),
        child: Actions(
          actions: {
            OpenLogPanelIntent: CallbackAction<OpenLogPanelIntent>(
              onInvoke: (_) {
                opened++;
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: const Scaffold(body: SizedBox()),
          ),
        ),
      ),
    ));

    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.backquote);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.backquote);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pump();

    expect(opened, 1);
  });
}
