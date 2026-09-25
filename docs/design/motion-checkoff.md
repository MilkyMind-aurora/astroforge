# 动效 26 项勾账表（MF6 收口 · 方案 §1.8 / §六）

> 逐项状态按「端」标注，证据为本会话实测 grep/读取的 `文件:行`。
> 状态口径：✅ 已实现｜⚠️ 部分/简化（附差异说明）｜❌ 未实现（附原因与裁定依据）。
> 曲线纪律：全部取自 tokens.yaml `motion`（全局唯六，禁自造），经 gen_design 三端产物下发。
> 时长红线自查：交互反馈 ≤300ms、转场 250~400ms、禁 ease-in 起步、入场错拍 30ms/项、全屏活光 ≤1（#26 唯一）——逐项落位见下。

## 勾账总表

| # | 动效 | 端 | 状态 | 证据（本会话实测） |
|---|---|---|---|---|
| 1 | 星野缓漂+流星 | Flutter | ✅ | `app/lib/core/starfield/starfield_view.dart:14-21,91-109`（uTime 驱动 ±2dp/4s、E1 流星 120s 掷 25%、弹层打开流星让位、失焦冻结）；参数源 `tokens.g.dart` AstroStarfield；golden 冻结 uTime=0（`app/test/golden_screens_test.dart`） |
| 1 | 星野 | TUI | ✅ | `tui/tui/ui/starfield.py:1-12`：seed.json 预生成坐标→静态 3 行星点框（终端不做循环动画=性能红线，§3.7），星符取自 icons.yaml 生成物 |
| 2 | 主题切换触点圆形扩散 | Flutter | ✅ | `app/lib/core/theme/astro_theme_scope.dart:99-150`（AstroThemeReveal：旧帧截屏冻结→触点→最远角 clip 圆形擦除 320ms，裁切不缩放；reduced-motion 瞬时切换） |
| 3 | 液态 Tab | Flutter | ✅ | `app/lib/presentation/widgets/liquid_chips.dart:29`（LiquidChipRow）+ `monitor_sheet.dart:17`（range 液态 Tab #3） |
| 4 | 侧栏选中胶囊滑移 | Flutter | ✅ | `app/lib/presentation/shell/astro_rail.dart:43-59`（SpringSimulation，SPRING_SOFT 260/0.85——tokens.motion.spring_soft） |
| 4 | 侧栏胶囊滑移 | TUI | ✅ | `tui/tui/shell/sidebar.py:106`（capsule.animate offset，T_PRESS 120ms） |
| 5 | 流式合批上屏 | Flutter | ✅ | `app/lib/data/ai/stream_batcher.dart:6`（StreamBatcher 2~4 token/帧合批）+ AI 抽屉消费 |
| 5 | 流式合批 | TUI | ✅ | `tui/tui/panels/ai_drawer.py:311`（_drain_buffer：RichLog 增量 append，禁整块重排） |
| 6 | 思考三点错相 | Flutter | ✅ | `app/lib/presentation/ai/ai_drawer.dart:545`（alpha 0.3→1 循环 1.2s、错相 0.2s） |
| 6 | 思考帧 | TUI | ✅ | `tui/tui/panels/ai_drawer.py:34-35,319`（✶✷✸ 0.4s/帧 1.2s 循环，帧名取 icons.yaml） |
| 7 | 骨架+Shimmer | 双端 | ❌（裁定豁免） | 未实现。**依据 V1.1-4 UX 评审「本地延迟三档」**：瞬时档（<100ms，全部 REST 查询）禁骨架屏/shimmer/全屏 loading，立即渲染+SWR——本项按裁定不实施。落点注释：`task_page.dart:17`、`history_page.dart:284`、`history_detail.dart:147` |
| 8 | 数字滚动 CountUp | Flutter | ✅ | `app/lib/presentation/monitor/monitor_sheet.dart:1087-1126`（400ms 仅首帧到达/range 切换；实时 1s 直接换值——UX 评审 CountUp 限定场景）；TUI 不适用（§1.8：直接更新） |
| 9 | 磁吸游标+码表 | Flutter | ✅ | `app/lib/presentation/monitor/monitor_sheet.dart:726,762,778`（<24dp 吸附 spring(300,0.55)+数值 mono tabular 联动） |
| 10 | 进度底色前推 | Flutter | ❌（token 就绪未接线） | `runningWashBg`（aurora@6%）已在 tokens 预计算（`tokens.g.dart:114,151`），但 presentation 层 grep 0 消费——「卡底色填充宽 0→100% 前推+推满提亮 160ms」完整动画未落位（欠债） |
| 10 | 进度提亮 | TUI | ⚠️ 离散近似 | `tui/tui/components/timeline.py:109,140`：完成瞬间提亮 160ms（先亮后定——Textual 无连续填充动画的最小近似） |
| 11 | 步骤条过冲 | Flutter | ✅ | `app/lib/presentation/widgets/step_timeline.dart:198,276`（scale 1→1.08→1 过冲回弹 ζ0.6） |
| 11 | 步骤过冲 | TUI | ✅（离散近似） | `tui/tui/components/timeline.py:6-7,140`（先亮 160ms 再落定，#11 的 TUI 离散近似） |
| 12 | 生长式弹出 | Flutter | ✅ | `app/lib/presentation/widgets/instruction_card.dart:5-7`（GrowIn：scale 0.85→1.02→1，SPRING_POP 320/0.72，pivot=触发位）+ `task_page.dart:389`（提交成功原地弹出任务卡） |
| 12 | 生长式 | TUI | ✅（离散近似） | `tui/tui/panels/ai_drawer.py:36,326`（GROW_STEP_S=0.06 指令卡逐行显现） |
| 13 | 列表错峰入场 | Flutter | ✅ | `app/lib/presentation/pages/home_page.dart:413-448`（_StaggerIn：translateY 16→0+fade；stagger 150ms/元素=§5.2 屏级规格四元素） |
| 13 | 列表错峰 | TUI | ✅ | `tui/tui/plugins/home/page.py:8,23`（STAGGER_S=0.03，九宫格 30ms/行，一次性入场） |
| 14 | 状态文字推进 | 双端 | ❌ | 双端 grep（AnimatedSwitcher/文字推进/旧字）0 命中——任务状态迁移的文字滑动未落位（欠债；状态变更当前为原位替换） |
| 15 | 成功勾选一笔画出 | 双端 | ❌ | 双端 grep（PathMeasure/extractPath）0 命中——成功勾选描画动画未落位（欠债；成功态当前为静态 ✓ 徽标） |
| 16 | 撤销倒计时进度化 | Flutter | ✅ | `app/lib/presentation/widgets/undo_bar.dart:7-8,87`（10s→0 线性、禁缓动——倒计时语义；撤销=取消新任务） |
| 16 | 撤销倒计时 | TUI | ✅ | `tui/tui/plugins/history/page.py:8,36`（UNDO_WINDOW_S=10，#hd-undo 熔金条） |
| 17 | 边缘高亮跑圈 | TUI | ✅ | `tui/tui/shell/boot.py:18-23,64`（跑圈 4 帧×0.3s=1.2s 一圈，dur-loop 档，探活期唯一循环动画位） |
| 17 | 边缘高亮跑圈 | Flutter | ⚠️ 简化 | 连接引导/引擎唤醒用环形进度+阶段化文字（`home_page.dart:621` 点火卡、`home_page.dart:1107` 拉起中 CircularProgressIndicator），无 sweepGradient 跑圈——功能语义等价（进行态可感知），视觉规格未对齐（欠债级差异） |
| 18 | 极光横幅扫过 | 双端 | ❌ | 任务完成 hero 横幅（白名单位①）未实现；高光 900ms 扫过无。AstroGalaxy 现消费仅 AI 抽屉头饰线（`ai_drawer.dart:327`，白名单位②）与 TUI 启动横幅（`boot.py:22`，白名单位③，静态行级三停驻渐变）——渐变白名单纪律未破，但「任务完成时刻」的多通道触达缺横幅位（欠债） |
| 19 | 弹层拖回双判 | Flutter | ✅ | `app/lib/presentation/ai/model_sheet.dart:69-108`（位移>96dp 或 速度>1000dp/s 满足其一即关，取值 AstroInteraction.sheetDismiss*） |
| 20 | 重连横幅挤压进场 | Flutter | ✅ | `app/lib/presentation/shell/disconnect_banner.dart:7-19`（AnimatedSize 高度 0→banner 挤压进场，内容下移让位，恢复滑出） |
| 20 | 断连反馈 | TUI | ⚠️ 按方案状态栏语义 | TUI 无顶部横幅位——方案 §3.1 规定状态栏 `◌重连中` nova 闪（`tui/tui/app.py:207` reconnect + 状态栏重连态）；「挤压进场」语义由状态栏变色承担 |
| 21 | Container Transform | Flutter | ✅ | `app/lib/presentation/pages/history_page.dart:411-421`（animations.OpenContainer，fadeThrough 300ms，行卡原地放大成详情页） |
| 22 | 图例点切 alpha | Flutter | ✅ | `app/lib/presentation/monitor/monitor_sheet.dart:823,846`（alpha 1→0.15，TWEEN_COLOR 150ms） |
| 23 | 柱高平滑长高 | Flutter | ✅ | `app/lib/presentation/monitor/monitor_sheet.dart:971-1035`（range 切换柱高原值→新值 SPRING_SOFT，禁整排重画） |
| 24 | 汉堡变叉 | 双端 | ❌（无落位） | grep AnimatedIcons/汉堡 = 0。桌面端 AI 抽屉经轨底入口/Ctrl+Shift+A 唤起（`app_scaffold.dart:56-63`），抽屉内无汉堡钮——规格里的「抽屉钮」在 IA 8→5 后无落位；如后续加抽屉内收起钮需补此动效 |
| 25 | 星仔帧动画 | TUI | ✅ | `tui/tui/ui/mascot.py:20-54,134`（idle/idle_blink/happy/error/sleeping ASCII 帧 + quotes.yaml 台词库外置） |
| 25 | 星仔（星球化） | Flutter | ✅ | `app/lib/core/mascot/starling_engine.dart:79-179`（V2 纯函数 sampleStarling(t)：7 业务态×表情基元两层；身体永不 overshoot）+ starling_painter 遮罩眼睛/星环粒子；golden frozenAt 断言 |
| 26 | 输入条聚焦光晕 | Flutter | ✅ | `app/lib/presentation/pages/home_page.dart:530-600`（聚焦 aurora 1.5dp+8%→12% 呼吸 2.4s，唯一活光；失焦停表防空转；reduced-motion 静态 8%） |
| 26 | 输入聚焦 | TUI | ✅（等价） | 聚焦盒描边升档 aurora（V1.2-1 borderActive：`tui.border_levels.active=aurora`→`tokens.tcss .border-active`）；光晕 alpha 呼吸为 Flutter 专属（终端无 alpha 合成） |

## CLI 动效（§六：CLI 落地 3 项）

| 项 | 状态 | 证据 |
|---|---|---|
| 进度刷新节流 100ms | ✅ | `tokens.yaml motion.cli.progress_throttle_ms=100` → 生成段 `modules/_shared/star_console.py` STAR_MOTION（gen_design 渲染；ui_doctor gen-idempotent 通过） |
| spinner 80ms/帧 | ✅ | 同上 `spinner_frame_ms=80` |
| 星符/分级着色 | ✅ | 生成段 STAR_TOKENS（dark/light 全色板）+ STAR_ICONS（icons.yaml 全表）；TTY 检测失败回退纯文本（stdout 契约字节不变） |

## 统计与结论

- **✅ 完整/近似实现：20 项**（#1-6、8、9、11、12、13、16、17-TUI、19、20、21、22、23、25、26；其中 #10/#12/#13/#17 含 TUI 离散近似，符合「Textual 无弹簧」的端差异）
- **⚠️ 部分/简化：2 项**（#10-TUI 提亮近似 ✅ 但 Flutter 端缺前推动画；#17-Flutter 环形进度替代 sweep 跑圈；#20-TUI 按状态栏语义）
- **❌ 未实现：5 项**——
  - #7 骨架+Shimmer：**裁定豁免**（V1.1-4 延迟三档：瞬时档禁骨架屏），非欠债；
  - #14 状态文字推进、#15 成功勾选一笔画出、#18 任务完成极光横幅、#24 汉堡变叉（无落位）：**真实欠债**，列入 MF6 遗留债清单。
- 全屏活光纪律：仅 #26 输入条聚焦光晕一处 ✅（金测截图双主题均可复核）。
