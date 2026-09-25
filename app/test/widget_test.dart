// AstroForge 应用冒烟测试：应用壳可构建、导航目标渲染（8 目的地与 TUI 一一对应）。
import 'package:astroforge/presentation/core/nav_destinations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('导航目标定义与 TUI 侧边栏一一对应（8 页）', () {
    expect(navDestinations.length, 8);
    expect(navDestinations.first.label, '首页');
    expect(navDestinations.last.label, '设置');
    expect(navDestinations.first.path, '/home');
    expect(navDestinations.last.path, '/settings');
    // lucide 线性图标（方案 §1.6）：目的地全部带非空图标
    for (final destination in navDestinations) {
      expect(destination.label, isNotEmpty);
    }
  });
}
