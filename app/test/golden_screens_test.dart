// 双主题金测截图（MF6 收口：方案 §5.8 门禁④「每屏双主题截图」+ §1.5 星野降级
// 规则「golden test 冻结 uTime=0」+ 星仔规格 V2-2 frozenAt 单帧断言）。
//
// 帧冻结机制【硬性】：harness 注入 MediaQuery.disableAnimations=true——
// StarfieldView/StarlingView 的 reduced-motion 路径把业务时钟恒置 t=0
// （星野 Canvas 直绘 seed.json 坐标、uTime=0；星仔 sampleStarling(t=0) 单帧），
// 错峰入场/光晕呼吸全部瞬时到位，输出与运行时刻无关 → 像素级可复现。
//
// 契约纪律：5 个 IA 页面与壳层组件全部用真实实现；harness 只在两处与本机
// 测试环境绑定，均如实声明：
// ①字体：flutter_test 默认 Ahem 方块字，这里从本机字体注册金测族（CJK 主字 +
//   星符 fallback 族 + mono 顶替）；生产端正文跟随系统 CJK、mono 打包
//   JetBrainsMono 子集（pubspec 当前尚未打包——已知债，见 MF6 notes）。
// ②数据：apiClientProvider 注入 FakeApiClient（离线金测环境，无服务进程）；
//   connectionProvider 注入未连接的 ForgeWebSocket（app_providers 的测试缝），
//   仪表胶囊显示「重连中」+ 最后已知采样——禁伪造「已连接」。
//
// 再生成（本机 Windows）：
//   cd app && flutter test --update-goldens test/golden_screens_test.dart
// 校验（无 --update-goldens 时逐字节比对；非 Windows 跳过——字体基线绑 Windows）：
//   cd app && flutter test test/golden_screens_test.dart
// 产物落盘：docs/design/screenshots/<dark|light>_<screen>.png
//
// 确定性纪律：FakeApiClient 的时间戳必须距今 >24h——历史卡相对时刻标签
// 按「N 天前」天粒度变化（_relativeTime 用 DateTime.now()），24h 内稳定。
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:astroforge/core/app_providers.dart';
import 'package:astroforge/core/design/design.dart';
import 'package:astroforge/core/router.dart';
import 'package:astroforge/data/api_client/dio_client.dart';
import 'package:astroforge/data/ws_client/ws_client.dart';

/// 金测字体族：本机注册名，与生产字体族名隔离（禁污染生产 fontFamily）。
const String _kGoldenCjk = 'AstroGoldenCjk';
const String _kGoldenSymbol = 'AstroGoldenSymbol';

const String _goldenDir = '../../docs/design/screenshots';

void main() {
  SharedPreferences.setMockInitialValues(<String, Object>{});

  setUpAll(() async {
    await loadGoldenFonts();
  });

  // 基线在 Windows 生成（CJK/mono/星符字形绑定本机字体集）；跨平台逐字节
  // 比对必挂——其他平台跳过比对，再生成仍走 --update-goldens（诚实降级）。
  final platformSkip = Platform.isWindows
      ? null
      : 'golden 基线由 Windows 生成（字体渲染存在平台差异）';

  for (final mode in [ThemeMode.dark, ThemeMode.light]) {
    final prefix = mode == ThemeMode.dark ? 'dark' : 'light';
    for (final (path, screen) in const [
      ('/home', 'home'),
      ('/tasks', 'tasks'),
      ('/pipeline', 'pipeline'),
      ('/history', 'history'),
      ('/settings', 'settings'),
    ]) {
      testWidgets(
        '双主题截图 $prefix $screen（uTime=0 冻结帧）',
        (WidgetTester tester) async {
          if (!Platform.isWindows) {
            // 保留跳过原因（testWidgets 的 skip 只收 bool）：
            // golden 基线由 Windows 生成，其他平台仅支持 --update-goldens 再生成。
            markTestSkipped(platformSkip!);
            return;
          }
          final overrides = <Override>[
            // 离线金测数据源（FakeApiClient：env-check 9/9、引擎可达、终态任务）
            apiClientProvider.overrideWith((ref) => FakeApiClient()),
            // 注入未连接 WS（app_providers 测试缝）：断连态如实呈现，禁伪造「已连接」
            connectionProvider.overrideWith(
              (ref) =>
                  ConnectionController(ws: ForgeWebSocket(path: '/ws/monitor')),
            ),
            // 主题模式：AstroThemeController 真实现 + setMode 置端点值
            // （mock prefs 下持久化为空操作，主题 lerp 落在 t=0/1 端点）
            astroThemeModeProvider.overrideWith((ref) {
              final controller = AstroThemeController();
              controller.setMode(
                mode == ThemeMode.dark
                    ? AstroThemeMode.dark
                    : AstroThemeMode.light,
              );
              return controller;
            }),
          ];
          final container = ProviderContainer(overrides: overrides);
          addTearDown(container.dispose);

          await _pumpGoldenShell(tester, container, mode);
          if (path != '/home') {
            container.read(routerProvider).go(path);
          }
          // 冻结帧等待：错峰入场（最长 600ms）+ 轨道胶囊弹簧落定 + 异步 setState
          // 全部落定后才截帧（禁在动画中途截图）；时钟本身冻结在 t=0。
          await tester.pump(const Duration(milliseconds: 400));
          await tester.pump(const Duration(milliseconds: 800));
          await tester.pump(const Duration(milliseconds: 800));

          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile('$_goldenDir/${prefix}_$screen.png'),
          );
        },
      );
    }
  }
}

/// 金测根壳：与 AstroThemeScope 同构（MaterialApp.router + AstroPaletteScope），
/// 差异仅两处——①textTheme 显式挂金测字体族与星符 fallback；
/// ②MediaQuery.disableAnimations=true 注入（uTime=0 冻结的唯一开关，
/// 生产端该值来自系统无障碍设置）。
Future<void> _pumpGoldenShell(
  WidgetTester tester,
  ProviderContainer container,
  ThemeMode mode,
) async {
  tester.view.physicalSize = const Size(1280, 800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final isDark = mode == ThemeMode.dark;
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        title: 'AstroForge · 衍星台',
        // 金测等价 release：debug 模式默认右上角 DEBUG 横幅会污染截图基线
        debugShowCheckedModeBanner: false,
        themeMode: mode,
        theme: withGoldenFonts(AstroTheme.light()),
        darkTheme: withGoldenFonts(AstroTheme.dark()),
        routerConfig: container.read(routerProvider),
        builder: (context, routerChild) {
          final palette = isDark ? AstroPalette.dark : AstroPalette.light;
          return MediaQuery(
            // uTime=0 冻结开关：星野/星仔/错峰/光晕全部走 reduced-motion 单帧路径
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: AstroPaletteScope(
              palette: palette,
              darkProgress: isDark ? 1.0 : 0.0,
              child: routerChild!,
            ),
          );
        },
      ),
    ),
  );
}

/// 供金测复用（调试测试）：textTheme 显式挂金测字体族与星符 fallback。
ThemeData withGoldenFonts(ThemeData base) {
  const fallback = [_kGoldenSymbol, _kGoldenCjk];
  TextStyle? fam(TextStyle? style) =>
      style?.copyWith(fontFamily: _kGoldenCjk, fontFamilyFallback: fallback);
  return base.copyWith(
    textTheme: base.textTheme.apply(
      fontFamily: _kGoldenCjk,
      fontFamilyFallback: fallback,
    ),
    primaryTextTheme: base.primaryTextTheme.apply(
      fontFamily: _kGoldenCjk,
      fontFamilyFallback: fallback,
    ),
    // 组件级样式槽（chip/tooltip/snackbar 的 labelStyle 不经 textTheme，
    // 金测环境空 family 会回落 Ahem 方块字——逐槽补齐）
    chipTheme: base.chipTheme.copyWith(labelStyle: fam(base.chipTheme.labelStyle)),
    tooltipTheme: base.tooltipTheme.copyWith(textStyle: fam(base.tooltipTheme.textStyle)),
    snackBarTheme: base.snackBarTheme.copyWith(
      contentTextStyle: fam(base.snackBarTheme.contentTextStyle),
    ),
  );
}

// ============================================================
// 金测字体注册（本机字体 → FontLoader；替代 Ahem 方块字）
// ============================================================

/// 供金测复用（调试测试）单独调用。
Future<void> loadGoldenFonts() async {
  // CJK 主字：微软雅黑（最接近生产「正文跟随系统 CJK」的 Windows 形态），
  // 等线 TTF 兜底（单面 TTF，FontLoader 必可载）。
  var ok = await _loadFamily(_kGoldenCjk, const [
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/msyhbd.ttc',
  ]);
  if (!ok) {
    ok = await _loadFamily(_kGoldenCjk, const [
      'C:/Windows/Fonts/Deng.ttf',
      'C:/Windows/Fonts/Dengb.ttf',
    ]);
  }
  if (!ok) {
    fail('金测字体不可用：未找到 msyh/Deng（截图会退化成 Ahem 方块字，拒绝产出）');
  }

  // 星符/几何符号 fallback：Segoe UI Symbol（icons.yaml 星符全集承载字体；
  // 生产端由 Windows 字体回退链天然命中，测试端需显式注册）。
  await _loadFamily(_kGoldenSymbol, const ['C:/Windows/Fonts/seguisym.ttf']);

  // mono 顶替：生产 mono_family=JetBrainsMono（pubspec 尚未打包——债），
  // 金测把 Consolas 注册到该族名下，tabular 数字按真实等宽渲染。
  await _loadFamily(AstroType.monoFamily, const [
    'C:/Windows/Fonts/consola.ttf',
    'C:/Windows/Fonts/consolab.ttf',
  ]);

  // 默认族名兜底：部分 Material 子树（OpenContainer 闭态 Material、ChoiceChip、
  // 无 family 的星符 Text）不走 textTheme.apply 出来的字体族——显式 family 的
  // 回落到 'Roboto'，空 family 的回落到测试引擎缺省 'Ahem'。把 CJK + 星符字体
  // 注册到这两个族名下，等价于生产端「系统字体回退链」行为；仅测试环境生效。
  for (final family in const ['Roboto', 'Ahem']) {
    await _loadFamily(family, const [
      'C:/Windows/Fonts/msyh.ttc',
      'C:/Windows/Fonts/msyhbd.ttc',
      'C:/Windows/Fonts/seguisym.ttf',
    ]);
  }

  // lucide 图标字体（包内 font 声明在测试引擎下以包限定族名注册才生效——
  // 实测 FontLoader('Lucide') 仍渲染方块，须双名注册，见 probe 结论）
  final lucideData =
      await rootBundle.load('packages/lucide_icons_flutter/assets/lucide.ttf');
  for (final family in const [
    'Lucide',
    'packages/lucide_icons_flutter/Lucide',
  ]) {
    final loader = FontLoader(family)
      ..addFont(Future<ByteData>.value(lucideData));
    await loader.load();
  }
}

Future<bool> _loadFamily(String family, List<String> paths) async {
  final loader = FontLoader(family);
  var count = 0;
  for (final path in paths) {
    final file = File(path);
    if (!file.existsSync()) continue;
    final bytes = file.readAsBytesSync();
    loader.addFont(Future<ByteData>.value(ByteData.view(bytes.buffer)));
    count++;
  }
  if (count == 0) return false;
  await loader.load();
  return true;
}

// ============================================================
// 离线金测数据源（终态任务/9 项体检/引擎可达；口径见文件头注释）
// ============================================================

class FakeApiClient extends ApiClient {
  @override
  Future<Map<String, dynamic>> health() async =>
      {'db': true, 'version': 'v0.1.0-golden', 'uptime_s': 3600};

  @override
  Future<Map<String, dynamic>> engineStatus() async =>
      {'reachable': true, 'current_model': 'qwen2b'};

  @override
  Future<Map<String, dynamic>> envCheck() async {
    return {
      'ok_count': 9,
      'total': 9,
      'items': [
        for (final (name, detail) in const [
          ('Python 3.12', '3.12.10'),
          ('Conda', 'env_astroforge 就绪'),
          ('PostgreSQL', '16 · astroforge 库已连接'),
          ('Chromium 浏览器', '128.0 · Scrapling 渲染可用'),
          ('MinerU 模型目录', 'models/mineru 就绪'),
          ('AI 模型', 'qwen2b · ornith9b 已下载'),
          ('anydoc 二进制', 'v0.2.4'),
          ('DOCX 模板（5 套内置）', 'tech_doc 等 5 套就绪'),
          ('数据目录', 'data/raw · data/output 可写'),
        ])
          {'name': name, 'ok': true, 'detail': detail},
      ],
    };
  }

  @override
  Future<List<dynamic>> listTasks({int page = 1, String? status}) async {
    // 全部终态（success/failed/canceled）：非终态任务会触发历史页 WS 订阅
    // （金测环境禁真实 socket）；失败流水线任务由 taskDetail 提供「停于步骤」。
    return [
      {
        'task_uuid': '9f2c1a7e3b8d4e6fa1b2c3d4e5f60718',
        'task_type': 'spider_site',
        'title': 'Vue 官方文档整站结构化',
        'status': 'success',
        'progress': 100,
        'mode': 'standalone',
        'config': {'output_dir': 'data/output/site'},
        'started_at': '2026-09-01T09:12:00',
        'finished_at': '2026-09-01T09:14:08',
        'created_at': '2026-09-01T09:12:00',
      },
      {
        'task_uuid': '4d8e0b6a2c7f4913ab5c8d9e0f1a2b34',
        'task_type': 'mineru',
        'title': 'PDF 批量解析 · 论文 12 篇',
        'status': 'failed',
        'progress': 62,
        'mode': 'pipeline',
        'config': {'output_dir': 'data/output/mineru_out'},
        'error_code': 3004,
        'started_at': '2026-09-01T10:02:00',
        'finished_at': '2026-09-01T10:05:41',
        'created_at': '2026-09-01T10:02:00',
      },
      {
        'task_uuid': '77b3d9f1e5a24c608d7b9c0d1e2f3a45',
        'task_type': 'md2docx',
        'title': '技术文档出库 · tech_doc 模板',
        'status': 'canceled',
        'progress': 0,
        'mode': 'standalone',
        'config': {'output_dir': 'data/output/docx_out'},
        'started_at': '2026-09-01T08:40:00',
        'finished_at': '2026-09-01T08:41:12',
        'created_at': '2026-09-01T08:40:00',
      },
    ];
  }

  @override
  Future<Map<String, dynamic>> taskDetail(String taskUuid) async {
    // 流水线失败任务的「停于步骤」补拉数据源（steps.status 逐个判读）
    return {
      'task_uuid': taskUuid,
      'steps': [
        {'name': '爬取章节', 'status': 'success'},
        {'name': '解析 PDF', 'status': 'success'},
        {'name': '转换 DOCX', 'status': 'failed'},
        {'name': '入库归档', 'status': 'pending'},
      ],
    };
  }

  @override
  Future<List<dynamic>> listPipelines() async {
    return [
      {
        'name': 'academic_paper',
        'title': '学术论文采集',
        'description': '论文页爬取 → MinerU 解析 → MD 归档',
        'steps': [
          {'name': '爬取论文页', 'module': 'spider_page'},
          {'name': '解析 PDF', 'module': 'mineru'},
          {'name': '归档 Markdown', 'module': 'anydoc'},
        ],
      },
      {
        'name': 'office_batch',
        'title': '办公批量转换',
        'description': 'Office 批量入库 → md2docx 出库',
        'steps': [
          {'name': '入库 anydoc', 'module': 'anydoc'},
          {'name': '出库 md2docx', 'module': 'md2docx'},
        ],
      },
    ];
  }

  @override
  Future<Map<String, dynamic>> configSummary() async {
    return {
      'md2docx': {'default_template': 'tech_doc'},
      'monitor': {'memory_warning_gb': 10, 'memory_critical_gb': 12},
      'system': {'task_concurrency': 2},
      'ai': {'default_model': 'qwen2b', 'idle_timeout': 1800},
    };
  }

  @override
  Future<Map<String, dynamic>> listTemplates() async {
    return {
      'items': [
        for (final (key, name, scene) in const [
          ('tech_doc', '技术文档', '研发手册/API 文档'),
          ('academic', '学术论文', '期刊/学位论文'),
          ('math_model', '数模论文', '竞赛论文排版'),
          ('general', '通用文档', '默认模板'),
          ('formal', '正式报告', '对外提交'),
        ])
          {'key': key, 'name': name, 'scene': scene},
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> monitorHistory(String range) async =>
      {'points': const <dynamic>[]};

  @override
  Future<Map<String, dynamic>> listAppSettings() async =>
      {'items': const <dynamic>[]};
}
