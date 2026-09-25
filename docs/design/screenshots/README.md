# 双主题截图（MF6 收口留档）

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

## 再生成与校验

```bash
cd app
flutter test --update-goldens test/golden_screens_test.dart   # 再生成（写回本目录）
flutter test test/golden_screens_test.dart                    # 逐字节比对校验
```

## 与生产渲染的两处已声明差异（诚实留痕）

1. **字体**：flutter_test 默认 Ahem 方块字。金测从本机字体注册：CJK 主字
   （msyh/Deng）挂 `AstroGoldenCjk` 族与 textTheme；星符（Segoe UI Symbol）作
   fallback；Consolas 顶替 `mono_family=JetBrainsMono`（pubspec 尚未打包
   JetBrainsMono——已知债）；并将 CJK+星符字体同时注册到引擎缺省族名
   `Roboto`/`Ahem` 下（等价生产端系统字体回退链）。非 Windows 平台跳过比对
   （`skip`，基线绑 Windows 字体集）。
2. **数据**：离线金测环境无服务进程——`apiClientProvider` 注入 FakeApiClient
   （env-check 9/9、引擎可达、终态任务），`connectionProvider` 注入未连接 WS
   （app_providers 测试缝），右上仪表胶囊如实显示「重连中」，不伪造「已连接」。

## 已知渲染缺陷（金测环境特有，生产不受影响）

- **历史页任务卡的状态徽标星符（✓/✕/⊘）与行尾 ▸ 渲染为方块**：这些卡片经
  `animations.OpenContainer` 闭态 `Material` 包裹，其 `AnimatedDefaultTextStyle`
  解析到引擎缺省字体路径（family=Roboto、无 fallback），其中 msyh 缺
  ✓/✕/⊘/▸ 字形；已实测测试引擎对同族多字面不逐字形回退（探针：
  `Roboto=[seguisym,msyh]` 时符号可显但 CJK 反变方块）。生产端 Windows 系统
  字体回退链正常命中 Segoe UI Symbol。

## 文件清单

| 文件 | 内容 |
| --- | --- |
| `dark_home.png` / `light_home.png` | 首页空态（星仔+问候+能力胶囊+输入条） |
| `dark_tasks.png` / `light_tasks.png` | 任务页（ChoiceChip+schema 表单+最近任务） |
| `dark_pipeline.png` / `light_pipeline.png` | 流水线页（模板卡+分步参数+时间线） |
| `dark_history.png` / `light_history.png` | 历史页（筛选 chips+任务卡流） |
| `dark_settings.png` / `light_settings.png` | 设置页（外观/引擎/服务分组卡） |

尺寸 1280×800（与 `main.dart` 默认窗口一致），DPR 1.0。
