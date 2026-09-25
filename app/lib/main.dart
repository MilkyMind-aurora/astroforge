import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'core/theme/astro_theme_scope.dart';

/// AstroForge Flutter 桌面端入口（Windows/macOS）。
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();
  const windowOptions = WindowOptions(
    size: Size(1280, 800),
    minimumSize: Size(1200, 800),
    title: 'AstroForge · 衍星台',
  );
  await windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
  });
  runApp(const ProviderScope(child: AstroForgeApp()));
}

class AstroForgeApp extends StatelessWidget {
  const AstroForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    // 星空主题 scope（tokens.g.dart + lerpPalette 250ms 全色板过渡；
    // theme.dart 已废弃——方案附录「对接点速查」；ColorScheme 手写禁 fromSeed）。
    // MaterialApp.router 由 scope 内部装配（routerProvider）。
    return const AstroThemeScope(child: SizedBox.shrink());
  }
}
