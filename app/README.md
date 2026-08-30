# AstroForge Flutter 桌面端

对接 Sidereal Core（127.0.0.1:8420）的图形客户端，编译目标：**windows + macos**（方案 3.10）。

## 开发运行

```bash
cd app
flutter pub get
flutter run -d windows   # 或 -d macos
```

## 已实现（骨架阶段）

- 星尘主题（明暗双套，Material 3）与 NavigationRail 8 页外壳
- Dio API 客户端（X-AstroForge-Token 注入 + 统一信封解析）
- WebSocket 客户端（指数退避重连 1s→60s + 45s 心跳超时）
- 首页真实调用 /system/health + /system/env-check，含连接引导态
- 监控页 fl_chart 曲线骨架（演示数据流，WS 接入属 Phase 9.5）
- AI 抽屉占位（流式气泡/指令卡片属 Phase 9.6）

## 已知限制（本地开发）

- **中文路径**：当前 Dart analysis server 在含中文的项目路径下会崩溃
  （LSP JSON 截断）。本地 analyze/test 请把 `lib/ test/ pubspec.yaml analysis_options.yaml`
  复制到 ASCII 路径的工程副本中执行；CI（GitHub Actions）为 ASCII 路径不受影响。
- `flutter create` 生成的 windows/macos runner 已入库；打包（Inno Setup / dmg）属 Phase 9.8。

## 测试

```bash
flutter test
```
