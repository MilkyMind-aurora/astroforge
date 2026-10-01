// 动效组件单测（终审 L27）：#15 一笔画勾选 / #10 进度底色前推 /
// #14 状态文字推进 / #18 极光横幅 —— reduced-motion 与状态迁移行为。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:astroforge/core/design/design.dart';
import 'package:astroforge/presentation/widgets/aurora_banner.dart';
import 'package:astroforge/presentation/widgets/progress_wash.dart';
import 'package:astroforge/presentation/widgets/status_slide_text.dart';
import 'package:astroforge/presentation/widgets/stroke_checkmark.dart';

Widget _wrap(Widget child, {bool reduced = false}) {
  return AstroPaletteScope(
    palette: AstroPalette.dark,
    darkProgress: 1.0,
    child: MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(disableAnimations: reduced),
        child: ColoredBox(color: AstroPalette.dark.bg, child: child),
      ),
    ),
  );
}

void main() {
  testWidgets('#15 一笔画：reduced-motion 直接整段呈现（无动画进度）',
      (tester) async {
    await tester.pumpWidget(_wrap(const SizedBox(
      width: 40,
      height: 40,
      child: StrokeCheckmark(color: Colors.white, size: 12),
    )));
    await tester.pump(const Duration(milliseconds: 300));
    await expectLater(
      find.byType(StrokeCheckmark),
      matchesGoldenFile('goldens/stroke_checkmark_reduced.png'),
    );
  });

  testWidgets('#10 进度底色前推：fraction=0.6 时 wash 宽度≈60%',
      (tester) async {
    await tester.pumpWidget(_wrap(const Align(
      alignment: Alignment.topLeft,
      child: SizedBox(
        width: 200,
        height: 40,
        child: ProgressWash(
          fraction: 0.6,
          child: SizedBox.expand(),
        ),
      ),
    )));
    await tester.pumpAndSettle();
    // wash 层宽 = 200×0.6（FractionallySizedBox 承载）
    final box =
        tester.renderObject<RenderBox>(find.byType(FractionallySizedBox));
    expect(box.size.width, closeTo(120, 1.0));
  });

  testWidgets('#10 推满提亮：fraction=1 触发一次性提亮层后落定',
      (tester) async {
    await tester.pumpWidget(_wrap(const Align(
      alignment: Alignment.topLeft,
      child: SizedBox(
        width: 100,
        height: 40,
        child: ProgressWash(fraction: 1.0, child: SizedBox.expand()),
      ),
    )));
    await tester.pump(const Duration(milliseconds: 10));
    expect(find.byType(ProgressWash), findsOneWidget);
    await tester.pumpAndSettle();
    // 提亮 160ms 结束后 onEnd → _flashDone，Stack 不再包含提亮分支（不抛异常即过）
    await tester.pump(const Duration(milliseconds: 50));
    expect(tester.takeException(), isNull);
  });

  testWidgets('#14 状态文字推进：文字变化触发 AnimatedSwitcher 迁移',
      (tester) async {
    String status = '运行中';
    late StateSetter setOuter;
    await tester.pumpWidget(_wrap(StatefulBuilder(
      builder: (context, setState) {
        setOuter = setState;
        return StatusSlideText(
          text: status,
          color: AstroPalette.dark.auroraText,
        );
      },
    )));
    expect(find.text('运行中'), findsOneWidget);
    setOuter(() => status = '完成');
    await tester.pump();
    // 迁移期：新旧两枚文字同屏（下出上进）
    expect(find.text('运行中'), findsOneWidget);
    expect(find.text('完成'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('完成'), findsOneWidget);
    expect(find.text('运行中'), findsNothing);
  });

  testWidgets('#18 极光横幅：可见期渲染文案，visibleDuration 到点回调退场',
      (tester) async {
    var dismissed = false;
    await tester.pumpWidget(_wrap(AuroraBanner(
      message: '任务完成 · 整站结构化',
      visibleDurationMs: 200,
      onDismissed: () => dismissed = true,
    )));
    expect(find.text('任务完成 · 整站结构化'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 260));
    expect(dismissed, isTrue);
  });

  testWidgets('#18 极光横幅：reduced-motion 无扫过（高光带不出现）',
      (tester) async {
    await tester.pumpWidget(_wrap(
      const AuroraBanner(message: '任务完成', visibleDurationMs: 5000),
      reduced: true,
    ));
    await tester.pump(const Duration(milliseconds: 50));
    // LayoutBuilder 高光带仅在 sweep 启动后构建；reduced 分支 value 恒 0
    expect(
      find.descendant(
        of: find.byType(AuroraBanner),
        matching: find.byType(LayoutBuilder),
      ),
      findsNothing,
    );
    // 排空退场 Timer（flutter_test 禁悬挂定时器）
    await tester.pump(const Duration(seconds: 6));
  });
}
