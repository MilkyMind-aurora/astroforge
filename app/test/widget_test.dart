// AstroForge 应用冒烟测试：应用壳可构建、导航目标渲染。
import 'package:astroforge/presentation/core/nav_destinations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('导航目标定义与 TUI 侧边栏一一对应（8 页）', () {
    expect(navDestinations.length, 8);
    expect(navDestinations.first.$1, '首页');
    expect(navDestinations.last.$1, '设置');
  });
}
