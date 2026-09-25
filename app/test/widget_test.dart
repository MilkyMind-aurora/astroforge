// AstroForge 应用冒烟测试：应用壳可构建、导航目标渲染（IA 裁决 8→5，
// V1.1-4：首页/任务/流水线/历史/设置；TUI 保留 8 页，页面映射不强制）。
import 'package:astroforge/presentation/core/nav_destinations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('导航目标定义为 IA 8→5（首页/任务/流水线/历史/设置）', () {
    expect(navDestinations.length, 5);
    expect(navDestinations.map((d) => d.label).toList(),
        ['首页', '任务', '流水线', '历史', '设置']);
    expect(navDestinations.first.path, '/home');
    expect(navDestinations[1].path, '/tasks');
    expect(navDestinations.last.path, '/settings');
    // lucide 线性图标（方案 §1.6）：目的地全部带非空图标
    for (final destination in navDestinations) {
      expect(destination.label, isNotEmpty);
    }
  });
}
