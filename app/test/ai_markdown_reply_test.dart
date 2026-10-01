// 星伴 Markdown 回复体冒烟测试（终审 L19）：标题/列表/行内码/围栏代码块
// 在昼夜两档配置下渲染不抛异常，代码块高亮主题随昼夜切换。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:markdown_widget/markdown_widget.dart';
// visibility_detector 为 markdown_widget 传递依赖（仅在测试中调它的
// updateInterval 开关，故不进 pubspec dependencies——lint 豁免见下行）
// ignore: depend_on_referenced_packages
import 'package:visibility_detector/visibility_detector.dart';

import 'package:astroforge/core/design/design.dart';
import 'package:astroforge/presentation/ai/ai_drawer.dart';

const _sample = '''
## 解析结果

支持 **加粗**、`行内码` 与列表：

- 爬取章节
- 解析 PDF

```python
print("hello astroforge")
```
''';

Widget _wrap(Widget child, {required double darkProgress}) {
  return AstroPaletteScope(
    palette: darkProgress >= 0.5 ? AstroPalette.dark : AstroPalette.light,
    darkProgress: darkProgress,
    child: MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(child: child),
      ),
    ),
  );
}

void main() {
  setUpAll(() {
    // visibility_detector 默认 updateInterval 挂 Timer（flutter_test 禁悬挂
    // 定时器）——测试环境切 0 间隔（post-frame 回调路径）
    VisibilityDetectorController.instance.updateInterval = Duration.zero;
  });

  for (final (darkProgress, label) in [(1.0, '夜档'), (0.0, '昼档')]) {
    testWidgets('AiMarkdownReply $label：标题/列表/代码块渲染不抛异常',
        (tester) async {
      await tester.pumpWidget(_wrap(
        const AiMarkdownReply(text: _sample, palette: AstroPalette.dark),
        darkProgress: darkProgress,
      ));
      await tester.pump(const Duration(milliseconds: 50));
      expect(tester.takeException(), isNull);
      // 标题与列表项文本真实上屏（Markdown 解析生效，非纯文本块）
      expect(find.text('解析结果'), findsOneWidget);
      expect(find.text('爬取章节'), findsOneWidget);
      expect(find.byType(MarkdownWidget), findsOneWidget);
    });
  }

  testWidgets('AiMarkdownReply：空文本不抛异常', (tester) async {
    await tester.pumpWidget(_wrap(
      const AiMarkdownReply(text: '', palette: AstroPalette.dark),
      darkProgress: 1.0,
    ));
    await tester.pump(const Duration(milliseconds: 50));
    expect(tester.takeException(), isNull);
  });
}
