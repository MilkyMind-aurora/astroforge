# 双主题截图（MF6 收口留档 · 终审 L26 改造后）

本目录是《前端优化方案V1-星空版》§5.8 门禁④「每屏双主题截图」的交付物：
Flutter 桌面端 5 个 IA 目的地（首页/任务/流水线/历史/设置）× 深空（dark）/晨昏
（light）双主题，由 golden test 冻结帧生成——**非手工截图**。

## 帧冻结纪律（uTime=0）

生成与比对全程注入 `MediaQuery.disableAnimations=true`：星野（`StarfieldView`）
与星仔（`StarlingView`）走 reduced-motion 路径把业务时钟恒置 t=0，星野 Canvas
直绘 `config/design/starfield/seed.json` 预生成坐标（uTime=0）、星仔
`sampleStarling(t=0)` 单帧——对齐 tokens.yaml `color.starfield.degrade_rule`
「golden test 冻结 uTime=0」与《星仔生命感与彩蛋系统规格 v1》V2-2 frozenAt 断言。
因此每张 PNG 与运行时刻无关，逐字节可复现（`flutter test` 校验两次通过）。

## 再生成与校验（任意平台，产物一致）

```bash
cd app
flutter test --update-goldens test/golden_screens_test.dart   # 再生成（写回本目录）
flutter test test/golden_screens_test.dart                    # 逐字节比对校验
```

## 与生产渲染的已声明差异（诚实留痕 · 终审 L26 后）

1. **字体（L26 改造：全部应用打包字体，无本机绑定、无平台 skip）**：金测只装载
   pubspec 打包的 JetBrainsMono latin（Regular/Medium/Bold，rootBundle→FontLoader），
   注册到生产 mono 族名与金测兜底族名（`AstroGoldenCjk`/`AstroGoldenSymbol`/
   `Roboto`/`Ahem`）。latin/数字按真实等宽字形渲染；**CJK 与星符（✦ ☄ ◈ ✓ 等）
   缺字回落测试引擎缺省 Ahem 方块——各平台字节一致（跨平台逐字节比对可过），
   代价是基线截图里 CJK/星符呈方块占位形态**。生产端不受影响：正文跟随系统
   CJK、星符走系统字体回退链、mono 走打包 JetBrainsMono（pubspec fonts 声明，
   OFL 许可见 `app/assets/fonts/LICENSE-JetBrainsMono-OFL.txt`）。此前的本机
   字体绑定（msyh/Deng/Segoe UI Symbol/Consolas 顶替）与非 Windows skip 已移除。
2. **数据**：离线金测环境无服务进程——`apiClientProvider` 注入 FakeApiClient
   （env-check 9/9、引擎可达、终态任务），`connectionProvider` 注入未连接 WS
   （app_providers 测试缝），右上仪表胶囊如实显示「重连中」，不伪造「已连接」。

## 文件清单

| 文件 | 内容 |
| --- | --- |
| `dark_home.png` / `light_home.png` | 首页空态（星仔+问候+能力胶囊+输入条） |
| `dark_tasks.png` / `light_tasks.png` | 任务页（ChoiceChip+schema 表单+最近任务） |
| `dark_pipeline.png` / `light_pipeline.png` | 流水线页（模板卡+分步参数+时间线） |
| `dark_history.png` / `light_history.png` | 历史页（筛选 chips+任务卡流） |
| `dark_settings.png` / `light_settings.png` | 设置页（外观/引擎/服务分组卡） |

尺寸 1280×800（与 `main.dart` 默认窗口一致），DPR 1.0。

## TUI 双主题过渡截图（终裁 B：Flutter 组代拍，**待 TUI 组覆盖**）

`ui_doctor screenshots-check`（工具链组扩充）预期本目录含 `tui_dark.png` /
`tui_light.png`。因 TUI 组施工轮已收束、无后续 ask 路由，经编排终裁（选 B）由
Flutter 组以 textual 无头导出代拍：`AstroForgeApp.run_test(size=120×32)` →
`export_screenshot()`（textual 官方 SVG 导出）→ Chromium 光栅化 PNG（注入
`text{font-size:12.2px}` 修正 CJK 回退字宽，消除 textLength 挤压叠字）。

**口径与限制（诚实留痕）**：
- 拍摄态为**服务不可达的离线真实态**（本机未运行 Sidereal Core，127.0.0.1:8420
  未监听）——非数据态；数据态截图已列入 visual-review.md needsHuman 清单；
- **过渡产物：TUI 组（tui/** 重写进行中）完工后应重拍并覆盖以下四张**，
  届时可换成有服务数据的工作台实态；
- 光栅化字体为 Chromium 回退链（Consolas/雅黑），非终端实拍像素——布局与
  配色取自 textual 官方 SVG 导出，字符定位逐格对齐。

| 文件 | 内容 |
| --- | --- |
| `tui_dark.png` / `tui_light.png` | 壳层离线态（首页离线提示+侧栏+快捷 chips；清单核对名） |
| `tui_dark_connect.png` / `tui_light_connect.png` | 连接引导态（ConnectPanel：星仔休眠+拉起指引+三动作钮；附加屏，不在清单内） |
