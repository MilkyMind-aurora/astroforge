import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'core/design/tokens.g.dart';
import 'core/router.dart';

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

class AstroForgeApp extends ConsumerWidget {
  const AstroForgeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'AstroForge · 衍星台',
      // 星空设计契约（tokens.g.dart 生成物；手写 ColorScheme，禁 fromSeed）
      theme: AstroTheme.light(),
      darkTheme: AstroTheme.dark(),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
