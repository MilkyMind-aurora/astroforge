# 视觉审计与走查留档（visual-review）

> 来源：视觉审计 9 项（high×3 / medium×3 / low×3）+ 双 persona 逐屏认知走查。
> 处置口径：能改的当场改；改动大或属新需求的登记 backlog 段并说明理由。
> 归档人：Flutter 组（app/** 所有者）；TUI 侧条目归 TUI 组（tui/** 现处其重写
> 窗口，Flutter 组不越界改其源码）。证据一律「文件:行 / 命令+输出」。
>
> **本轮走查（2026-10-02，persona 走查员）素材与口径（诚实留痕）**：
> - 素材：`docs/design/screenshots/` 全部 14 张（Flutter 金测 PNG×10 + TUI 过渡
>   PNG×4）逐一目验 + 双端前端代码流程通读；
> - 金测口径（`screenshots/README.md`）：CJK/星符在基线截图中为 Ahem 方块占位
>   ——**文案内容核自代码，排版可读性属 needsHuman**；数据为离线 Fake（恒显
>   「重连中」），非服务数据态；
> - 本会话实际执行过的检查：WCAG 对比度脚本重跑（命令与输出见审计①）+ 14 张
>   截图目验 + TUI 现状源码复核（B1/B3/B4 逐条 grep/读行）；**未跑**：全量
>   flutter test 套件、TUI pytest/ruff、textual 实机运行（纪律：编排汇合后统一
>   跑全量门禁）。

---

## ① 动笔三问 · 逐屏（Flutter 侧为主，TUI 对应页随行）

三问口径沿用方案《前端优化方案V1-星空版》：**这一屏的重色（渐变/品牌色）落在哪？
第一屏（above the fold）给了谁？这一屏剪掉了什么？**

| 屏 | Flutter 侧 | TUI 对应页 |
| --- | --- | --- |
| 首页 | 重色＝轨上选中胶囊 + 输入条聚焦光晕（全 App 唯一活光 #26）+ 体检 9/9 aurora 字；渐变 0 处。第一屏＝品牌时刻：星仔 120dp + Display 问候 + 4 能力胶囊 + 唯一活光输入条（`home_page.dart:19-22,254-318`）。剪掉＝任务列表/仪表盘（归历史/监控弹层）、引擎唤醒操作（收敛进发送钮状态机 `home_page.dart:86-155`） | 第一屏＝健康三问：体检九宫格 + 服务核心行 + 快捷 chips（`tui/plugins/home/page.py:4-13`）；剪掉＝对话式输入条（直达入口让位命令面板 `/` 与数字键） |
| 任务 | 重色＝选中 ChoiceChip（chipsSelectedBg 底 + aurora 字，液态指示 #3）+ 主钮 aurora 实底。第一屏＝类型 chips 行 + schema 表单首字段 + 最近任务卡（`task_page.dart:11-17`）。剪掉＝采集/解析/转换三独立页——IA 8→5 三合一（`nav_destinations.dart:5-8`） | 不合并：保留 2 采集/3 解析/4 转换三页（1-8 数字键肌肉记忆，`tui/app.py:68-75`）——双端纪律放宽为「数据互通+术语一致+快捷键语义对齐」 |
| 流水线 | 重色＝选中模板卡 aurora 描边 + 运行主钮。第一屏＝模板卡横滚 + 分步参数 + 时间线位（`pipeline_page.dart:9-13`）。剪掉＝逐步覆盖语义（服务契约 params 为运行级全局合并，每步预设只读展示——禁伪造） | 模板 OptionList → 步骤时间线（`tui/plugins/pipeline/page.py:3-12`），失败步骤单步续跑 |
| 监控 | **无独立屏**——IA 裁决降级为右上仪表胶囊（常驻连接态+CPU/内存）+ 点击展开星象台弹层（`gauge_capsule.dart:7-10`、`monitor_sheet.dart:4-18`）。第一屏＝KPI 行 4 卡 + 主曲线卡 + 吞吐柱状 + 告警条。剪掉＝进程列表（服务端无进程 API，禁伪造）。**金测 PNG 不含此屏**（`golden_screens_test.dart:57-65` 仅 5 目的地×2 主题）——本屏走查基于代码流，无像素证据 | 独立页 6 监控看板：KPI 行 + Sparkline + 进程表 + 告警区（`tui/plugins/monitor/page.py:3-17`） |
| 历史 | 重色＝选中筛选 chip + 状态星符（✓/✕/◌）。第一屏＝筛选 chips + 任务卡流 + 详情入口（`history_page.dart:15-22`）。剪掉＝产物列表区（服务端 artifacts 未暴露查询路由，如实不渲染——TUI 侧注明；Flutter 详情页同口径待真机核） | 筛选 chips + DataTable + 右滑详情抽屉 + 撤销倒计时（`tui/plugins/history/page.py:3-12`） |
| 设置 | 重色＝主题三选选中描边 + 开关 aurora。第一屏＝「外观」组卡（主题三选 + 星野/星仔开关），下接引擎/服务/路径分组（`settings_page.dart:8-13`）。剪掉＝危险操作直执行——Token 重置改滑动确认（D24 G7） | 「外观」主题 OptionList 热切 + 星仔/服务/路径分组（`tui/plugins/settings/page.py:3-10`） |

---

## ② 双 persona 逐屏走查记录

persona A＝**数模竞赛选手 · 图界面偏好**（要一眼可点的入口、图表反馈，怕终端感）；
persona B＝**终端极客 · 键盘优先**（要全程不碰鼠标，恨纯鼠标向交互）。
每屏四段：预期 → 看到 → 情绪 → 行动。像素判断依据截图；文案/交互语义依据代码。

### 首页（dark_home.png / light_home.png；TUI tui_dark.png 壳层首页）

- **A**：预期＝打开就有「新建任务」大按钮或仪表盘。看到＝星仔+大问候+四颗能力胶囊
  （爬取文档站/解析 PDF/转 Word/流水线）+居中输入条，右上两枚状态胶囊（红点
  「重连中」+ 青字「9/9 ✦」）。情绪＝第一眼「这是工具还是壁纸？」→ 5 秒内胶囊
  可点、输入条有占位句，转为「有点高级，不挡路」。行动＝点「解析 PDF」→ 代码
  契约预填跳任务页（`home_page.dart:142-146`）。断点＝右上两枚胶囊一红一青并排，
  语义全靠悬停 tooltip；问候文案在金测里是方块（口径所致，真机待人审）。
- **B**：预期＝如 CLI 般直进。看到＝无屏上快捷键速查。情绪＝先皱眉 → 试出
  Ctrl+1~5 / Ctrl+K / Ctrl+I / Ctrl+Enter / F5 / Esc 全套真绑定
  （`astro_shortcuts.dart:45-74`，Ctrl+Shift+A 为真实 Shortcuts 非假 tooltip），转好。
  行动＝Ctrl+I 聚焦输入条 → 输入 → Ctrl+Enter 发送，全程不碰鼠标。断点＝快捷键
  速查只能进 Ctrl+K 面板找，首轮发现成本高。

### 任务（dark_tasks.png / light_tasks.png）

- **A**：预期＝普通表单页。看到＝8 枚类型 chip 横排（选中枚深青底白字醒目）、
  URL/输出两输入框、青绿实底主钮、三张最近任务卡（✓100% / ✕62% / ◌0%，UUID
  等宽字体）。情绪＝清爽、不迷路。行动＝填 URL → 点主钮；点失败卡看进度。
  断点＝8 枚 chip 一字排开在 1280 宽下偏挤（「Office→MD」贴右缘），类型语义靠
  星符前缀，新用户需悬停 tooltip。
- **B**：预期＝CLI 参数式填法。看到＝chip+表单纯鼠标向。情绪＝「又是表单」→
  Tab 序可走完字段、主钮可聚焦回车；但 chip 无数字键直选。行动＝Tab 流提交。
  断点＝首页 SendIntent 由 composer 就近接管（`app_scaffold.dart:103-104`），
  任务页主钮的回车提交路径代码未见显式绑定——**存疑，未验证，待真机**。

### 流水线（dark_pipeline.png / light_pipeline.png）

- **A**：预期＝可视化流程图。看到＝两张模板卡（选中卡 aurora 描边 + 浅青 wash，
  卡面直列步骤链）+ 三行步骤参数（值列全「null」）+ 青绿运行钮 + 折叠 YAML 入口。
  情绪＝比 DAG 简单，能接受。行动＝点第二张卡切换模板。断点＝步骤参数值列全
  「null」首见会误以为坏了——代码口径为「预设只读展示、运行级全局合并」
  （`pipeline_page.dart:9-13`），空态文案观感待真机人审。
- **B**：预期＝YAML 直编。看到＝底部「自定义 YAML」折叠入口保留。情绪＝满意
  （不逼我走 GUI）。行动＝展开贴 YAML 保存。断点＝模板卡切换无键盘键位说明。

### 监控（Flutter 无金测 PNG——代码流走查；TUI 侧栏第 6 项）

- **A**：预期＝常驻图表区。看到＝轨上没有监控图标，只有右上小胶囊（连接态点 +
  CPU/内存 mono 值）。情绪＝愣 1 秒「监控去哪了」→ tooltip 告知点击展开星象台。
  行动＝点胶囊 → 弹层（KPI 四卡 + 双系列主曲线 + 柱状 + 告警条，
  `monitor_sheet.dart:4-18`）。断点＝**弹层无金测截图**，曲线/crosshair/告警观感
  全部需真机人审；金测里胶囊恒显「重连中」（离线口径），连接态视觉未获证。
- **B**：预期＝htop 式常驻全屏。看到＝TUI 有独立 6 监控看板整页（KPI+曲线+进程表
  +告警），Flutter 侧只有弹层。情绪＝TUI 反而更全——双端不对称但各有道理（
  `nav_destinations.dart:7-8` 双端纪律明示页面映射不强制）。行动＝按 6 直达。
  断点＝Sparkline 构造期取夜档常量（`monitor/page.py:190,194`），昼档热切后曲线
  可能不可见（审计⑤，未修）。

### 历史（dark_history.png / light_history.png）

- **A**：预期＝可筛选列表。看到＝6 枚筛选 chip（「全部」选中态清晰）+ 三张任务卡：
  成功绿 ✓、失败红 ✕ 且副题一行给全「停于步骤 3/4 · 耗时 3m41s · 错误 3004」、
  取消 ◌。情绪＝失败原因一行可见，安心。行动＝点行进详情（Container Transform，
  `history_page.dart:19-21`）。断点＝详情页金测未覆盖。
- **B**：预期＝journalctl 式过滤。看到＝chips + F5 刷新 + 右键菜单（重试/取消/
  导出日志/资源管理器中显示/复制 UUID，`history_page.dart:21-22`）。情绪＝右键
  菜单齐全，接近终端工作流。行动＝右键 → 复制 UUID。断点＝#16 撤销倒计时条在
  静态截图中不可见，需真机验证。

### 设置（dark_settings.png / light_settings.png）

- **A**：预期＝主题/服务开关。看到＝外观/引擎/服务三组卡；主题三选段控件
  （「夜」选中 aurora 描边）、星野/星仔开关、Token 重置滑确认钮。情绪＝分组干净，
  Kimi 式内嵌卡熟悉。行动＝切昼档 → 观察即时生效（截图证明两档 chrome 均完整，
  Flutter 侧无「昼页夜条」问题）。断点＝昼档开关钮深色偏重（审美项，人审）。
- **B**：预期＝配置文件级控制。看到＝GUI 开关为主 + 只读 config-summary 行。
  情绪＝中性；Tab 可走完段控件与输入。行动＝主题三选切档。断点＝无 vim 式键位
  （可接受，设置页低频）。TUI 侧 OptionList 主题热切 + app_settings 持久化
  （`tui/plugins/settings/page.py:6-10`）键盘流完整。

### TUI 壳层与连接引导（tui_dark.png / tui_light.png / tui_*_connect.png）

- **B**：预期＝1-8 直达 + 余光可知所在页。看到＝侧栏数字+健康点（全 ○，离线
  口径如实）、分隔线渲染为裸「──────」、**选中项仅文字加粗、无任何胶囊底**
  （审计② B1 的直接视觉证据）。情绪＝「选中态呢？」。行动＝按 5 切流水线，
  无法从余光确认所在页。断点＝本次复核现源码：全 tui 源 grep `.nav-link`/
  `.selected`/`#nav-capsule`/`.nav-sep` 的 CSS 规则 **零命中**（`tokens.tcss` 与
  各 `DEFAULT_CSS` 均无）——B1 在重写后代码中**仍未修**（`shell/sidebar.py:57,173,179-184`）。
- **A**：tui_light.png 昼档主内容为浅色、但顶栏/底栏仍为深色条（「昼页夜条」，
  审计③ B2 的视觉证据）；tui_light_connect.png 中「一键拉起服务」「复制诊断」
  两个 default 钮白底虚线在昼档近乎隐身（persona 走查新观察，归入 B2 重拍复核项）。
  断点＝该批为 TUI 重写前过渡产物（`screenshots/README.md` 终裁 B 代拍留痕），
  现 `tui/app.py:53-65,107-119` 已全量走 `$语义变量` + `get_css_variables` 主题
  热切——代码上 B2 主因已除，**须重拍双主题截图才能销项**。
- **连接引导**（双 persona 共评）：星仔 sleeping ASCII + z z、未响应地址
  `http://127.0.0.1:8420` 如实、Windows/macOS 拉起命令直给、三动作钮（重试连接
  选中态青底清晰/一键拉起/复制诊断，`shell/connect.py:97-99`）。情绪＝离线不
  崩、指路明确，好感。断点＝昼档 default 钮可见性（上文）。

---

## ③ 审计发现与处置记录（9 条）

| # | 审计项 | 处置 | 证据 |
| --- | --- | --- | --- |
| ① | [high] 昼档任务完成横幅文字对比度 FAIL | **【已修（我组文件）】** `app/lib/presentation/widgets/aurora_banner.dart`：两主题统一「夜档亮停驻 + 固定深字 `AstroPalette.dark.bg`」。**WCAG 脚本本会话重跑验证**（python 内联 WCAG 相对亮度/对比度脚本，取 `tokens.g.dart` 实际色值）：现状昼字 #F6F7FC on 昼停驻 #0C9B7E = **3.27 FAIL**（与审计一致）；深字 on 昼三停驻 = **5.75 / 4.14 / 3.51，两档不过**（证实昼渐变无合法字色）；修复后深字 on 亮停驻 = **12.21 / 6.05 / 10.04 全过**（13sp w500 AA 4.5 线；ask 记「12.2」即 12.21） | 修复落点 `aurora_banner.dart:63-69,74-84,117-141`；色值源 `tokens.g.dart:116-118`（昼停驻）`:153-155`（夜亮停驻）、`AstroPalette.light.bg`/`dark.bg`。余项→⑦ |
| ② | [high] TUI 侧栏选中态零样式：`.nav-link`/`.selected`/`#nav-capsule` 无 CSS 规则，胶囊 animate 落在无尺寸空 Static | **未修（TUI 组，backlog B1）**。本会话复核重写后源码仍零命中 | grep tui 源（py/tcss）`.nav-link`/`#nav-capsule`/`.nav-sep` 无规则；`shell/sidebar.py:54-57,168-184`；tui_dark.png 选中项仅加粗 |
| ③ | [high] TUI 昼档壳层 chrome 不随主题热切（「昼页夜条」）、`#nav-sep` 无规则、非 token 兜底色 | **代码已改写、截图待重拍（TUI 组，backlog B2）**。现 `tui/app.py:53-65` 壳层 CSS 全 `$card/$ink-600/$faint`，`:107-119` `get_css_variables` 随 `self.theme` 换档——原「代入序/兜底色」主因在重写中移除；过渡截图仍为旧实现产物 | `tui_light.png`/`tui_light_connect.png`（昼页夜条留档）；`tui/app.py:53-65,107-119`；`theme/astro_theme.py:33-56` |
| ④ | [medium] 星仔单一活跃无仲裁、满帧重绘 | **【已修（我组文件）】** `app/lib/core/mascot/starling_view.dart` 新增 `_StarlingDirector` 单例仲裁（最早注册存活实例持唯一动效位；失焦全停；reduced-motion 静帧不起表） | 修复会话记录：`flutter analyze lib` 0 issue；motion/markdown/eta 三测试 28 例 + golden_screens 10 例比对全过（**本会话未复跑，登记如原记录**） |
| ⑤ | [medium] TUI Sparkline min/max_color 构造期取夜档常量（昼档热切后不可见）；启动屏横幅恒取 `GALAXY["dark"]` | **未修（TUI 组，backlog B3）**。本会话读行确认仍在 | `tui/plugins/monitor/page.py:190,194`（`design.DARK[...]` 构造期常量）；`tui/shell/boot.py:46-47`（注释自称设计白名单位，仍恒夜档） |
| ⑥ | [medium] TUI 步骤级续跑文案缺「产物已保留/原地续跑」契约半句 | **未修（TUI 组，backlog B4）**。本会话读行确认仍在 | `tui/components/timeline.py:95,124,134`（仅「重试该步 ▶」）vs `app/lib/presentation/widgets/step_timeline.dart:176`（「从步骤 N『名』继续（前 N-1 步产物已保留）」） |
| ⑦ | [high·余项] 横幅昼档停驻取值回写 tokens.yaml galaxy 白名单位与规格 §四 | **待设计源回写（工具链组，backlog B5）**。tokens.yaml 为 gen_design 源、非 app/** 生成物，代改破坏「源-产物同源」；代码侧已先行统一亮停驻+深字（见①），源回写后 widget 可恢复读 token 昼值 | 本会话 WCAG 复跑：昼字 on 昼停驻 3.27 FAIL；深字 on 昼停驻 5.75/4.14/3.51 两档不过 |
| ⑧ | [low] 35 处 fontSize 裸字面量 | **【已修 30 处（我组文件）】** 收敛为 `AstroType.<step>.size` 同值引用（零视觉变化）；残余 8 处均星符/图标 glyph 尺寸 → backlog B6（[low·余项] 需先立 icon 字号 token 轴，强套字阶会改渲染尺寸） | 修复会话记录：`grep -rn "fontSize: 1[0-9]" lib`（排除 tokens.g.dart/AstroType）35→8 命中（**本会话未复跑该 grep**） |
| ⑨ | [low] 门禁留档链断（visual-review.md 缺失） | **【已修（我组文件）】** 本文件建立，三问/persona 走查/审计处置/needsHuman 四段齐备 | `docs/design/screenshots/README.md` 对本文件的引用自此可解析；本文件即产物 |

---

## ④ needsHuman（需人工/跨组跟进）

1. **TUI 数据态双主题截图重拍 + 人工比对**（B1/B2/B3 修复后）：现档
   `tui_*.png` 为重写前离线过渡产物。重拍后需人工比对：导航选中态胶囊（B1）、
   昼档 chrome 热切与 `tui_light_connect.png` 所见 default 钮昼档可见性（B2，本轮
   persona 走查新观察）、Sparkline 昼档曲线可见性（B3）。
2. **Flutter 监控弹层（星象台）无金测 PNG**：曲线/磁吸 crosshair/告警条/吞吐柱状
   的观感与可读性只有代码流证据，需真机人审补核。
3. **横幅修复真机观感**：本会话仅 WCAG 数值 + 代码验证；亮停驻+深字的实机可读
   性、3s 自动退场节奏、高光扫过与深字叠加观感需真机确认。
4. **金测 CJK=Ahem 方块口径**：全部屏的文案排版（换行/截断/星符回退）在基线截图
   中不可判，逐屏文案可读性需真机人审。
5. **任务页主钮回车提交路径**（persona B 断点）：代码未见显式绑定，未验证——
   需真机走查或补测试。
6. **全量门禁**：全量 flutter test 套件、TUI pytest/ruff、textual 实机冒烟本会话
   均未跑（纪律：编排汇合后统一跑）。
7. **B5 完成后的回读**：tokens.yaml 昼档取值回写后，`aurora_banner.dart` 应恢复
   按主题取 galaxy 停驻（当前为两主题统一亮停驻的过渡实现）。

---

## 附：上一轮处置留档（原表，证据口径不变）

### 已修（本轮落地）

| 审计项 | 落点 | 证据 |
| --- | --- | --- |
| [high] 昼档任务完成横幅文字对比度 FAIL | `app/lib/presentation/widgets/aurora_banner.dart`：两主题统一「夜档亮停驻 + 固定深字 `AstroPalette.dark.bg`」 | WCAG 脚本实测（本会话重跑复现，见审计①）：3.27 FAIL / 5.75·4.14·3.51 两档不过 / 修复后 12.21·6.05·10.04 全过 |
| [medium] 星仔单一活跃无仲裁、满帧重绘 | `app/lib/core/mascot/starling_view.dart`：新增 `_StarlingDirector` 单例仲裁（最早注册存活实例持唯一动效位，dispose 让渡；失焦 paused/inactive/hidden 全停、resumed 恢复；reduced-motion 静帧不起表），非活跃位零帧成本 | `flutter analyze lib` 0 issue；定向测试 28 例全过；golden_screens 10 例比对通过（reduced-motion 静帧像素不变）——修复会话执行，本会话未复跑 |
| [low] 35 处 fontSize 裸字面量 | 收敛 30 处为 `AstroType.<step>.size` 同值引用（零视觉变化）：32→display、15→titleSm、14→body、13→bodySm、12→caption、11→label | 修复会话 grep 35→8 命中；残余 8 处见 B6 |
| [low] 门禁留档链断（visual-review.md 缺失） | 本文件建立 | `screenshots/README.md` 引用可解析 |

### backlog（登记待办：改动大或属新需求/他人目录）

| # | 审计项 | 归属 | 理由与修法 | 证据 |
| --- | --- | --- | --- | --- |
| B1 | [high] 侧栏选中态零样式（详见审计②） | TUI 组 | tui/** 属 TUI 组重写窗口，Flutter 组不越界；修法：NavLink 补 height:3、`.selected` 补 `background:$container; text-style:bold`、`#nav-capsule` 补 1 列宽 aurora 底，修后重拍双主题截图 | `tui/tui/shell/sidebar.py:54-57,168-184`；tui_dark.png 导航区零填充 |
| B2 | [high] 昼档壳层 chrome 不随主题热切、`#nav-sep` 无规则、非 token 兜底色（详见审计③） | TUI 组 | 代码侧重写已移除主因（语义变量+热切注入），余 `#nav-sep` 无规则等；修后重拍双主题截图人工比对 | `tui/tui/app.py:53-65,107-119`；tui_light.png（昼页夜条留档） |
| B3 | [medium] Sparkline 构造期夜档常量、启动横幅恒夜档（详见审计⑤） | TUI 组 | 主题切换钩子按 `design.THEME_PALETTE[当前主题]` 重设颜色（或曲线自绘走 $ 变量）；banner 如为白名单位则在规格注明 | `tui/tui/plugins/monitor/page.py:190,194`；`tui/tui/shell/boot.py:46-47` |
| B4 | [medium] TUI 步骤级续跑文案缺契约半句（详见审计⑥） | TUI 组 | 按钮/tooltip 补齐 Flutter 同款句式「从步骤 N『名』继续（前 N-1 步产物已保留）」 | `tui/tui/components/timeline.py:95,124,134` vs `app/lib/presentation/widgets/step_timeline.dart:176` |
| B5 | [high·余项] 横幅昼档取值回写 tokens.yaml 白名单位与规格 §四（详见审计⑦） | 工具链组（设计源） | 源-产物同源纪律，不代改；回写后 widget 恢复读 token 昼值 | 本会话 WCAG 复跑数据（审计⑦） |
| B6 | [low·余项] 星符/图标字号无 token 轴（残余 8 处：`step_timeline.dart:249,266`、`gauge_capsule.dart:75`、`task_page.dart:784,871`、`instruction_card.dart:136`、`ai_drawer.dart:1024`、`astro_rail.dart:84`，值 9/10/16/18/22） | 工具链组（新 token 轴） | 先立「icon 字号」token（tokens.yaml + gen_design 三端下发）再收敛 | 残余清单行号如左 |

### 前轮合规走查存档（审计第 9 条旧痕，与新①②段互补）

- 重色落点：aurora 仅选中胶囊/主钮/进度/今日点；nebula 仅 AI 位；渐变仅 2 处
  白名单位且同屏 ≤1（aurora_banner + ai_drawer 头饰线）；星野 alpha 三档/seed
  预生成/uTime=0 冻结/失焦暂停均落地。
- 第一屏给了谁：TUI 首页=健康三问 ✓；Flutter 首页=品牌时刻 ✓；引擎休眠/连接
  引导/拖拽建任务等 P0 六项全部有实现。
- 剪掉了什么：Flutter IA 8→5 ✓；监控降级右上胶囊+弹层 ✓；TUI 居中 Modal 式
  AI/日志已改抽屉 ✓。
