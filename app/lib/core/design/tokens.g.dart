// ============================================================
// AstroForge 星空设计契约（生成物 —— scripts/gen_design.py，禁手改）
// 源：config/design/tokens.yaml + icons.yaml（sha256:8b1d8e5646fd）
// 纪律：app/lib 内除本文件外禁止 Color(0x…)（ui_doctor grep 断言）；
//       主题切换走 lerpPalette 全字段插值（§1.5 TWEEN_THEME 250ms）；
//       ColorScheme 手写、禁 fromSeed（星空设计系统规格 §六）。
// ============================================================
import 'package:flutter/material.dart';

/// 星空调色板（全字段；light/dark 两实例均由 tokens.yaml 解析）。
/// 字段 = 表面阶梯 + ink 阶梯 + 描边 + 五强调色（含 -Text 昼档变体）+ 实底文字
/// + alpha 合成色 + 银河渐变三停驻。
class AstroPalette {
  const AstroPalette({
    required this.bg,
    required this.sunken,
    required this.card,
    required this.container,
    required this.cardRaised,
    required this.containerPressed,
    required this.faint,
    required this.ink900,
    required this.ink600,
    required this.ink400,
    required this.stroke,
    required this.strokeFocus,
    required this.aurora,
    required this.auroraText,
    required this.nebula,
    required this.nebulaText,
    required this.hydrogen,
    required this.molten,
    required this.moltenText,
    required this.nova,
    required this.onAurora,
    required this.onNebula,
    required this.onHydrogen,
    required this.onMolten,
    required this.onNova,
    required this.chipsSelectedBg,
    required this.aiContainerBg,
    required this.errorWashBg,
    required this.runningWashBg,
    required this.alertWashBg,
    required this.galaxyStop0,
    required this.galaxyStop1,
    required this.galaxyStop2,
  });

  final Color bg;
  final Color sunken;
  final Color card;
  final Color container;
  final Color cardRaised;
  final Color containerPressed;
  final Color faint;
  final Color ink900;
  final Color ink600;
  final Color ink400;
  final Color stroke;
  final Color strokeFocus;
  final Color aurora;
  final Color auroraText;
  final Color nebula;
  final Color nebulaText;
  final Color hydrogen;
  final Color molten;
  final Color moltenText;
  final Color nova;
  final Color onAurora;
  final Color onNebula;
  final Color onHydrogen;
  final Color onMolten;
  final Color onNova;
  final Color chipsSelectedBg;
  final Color aiContainerBg;
  final Color errorWashBg;
  final Color runningWashBg;
  final Color alertWashBg;
  final Color galaxyStop0;
  final Color galaxyStop1;
  final Color galaxyStop2;

  /// 昼档（晨昏基调）。
  static const AstroPalette light = AstroPalette(
    bg: Color(0xFFF6F7FC),
    sunken: Color(0xFFE8EBF4),
    card: Color(0xFFFFFFFF),
    container: Color(0xFFEDEFF7),
    cardRaised: Color(0xFFFFFFFF),
    containerPressed: Color(0xFFE2E5F0),
    faint: Color(0xFFE0E4F0),
    ink900: Color(0xFF131629),
    ink600: Color(0xFF565B76),
    ink400: Color(0xFF606681),
    stroke: Color(0xFFC9CEE4),
    strokeFocus: Color(0xFF3A4066),
    aurora: Color(0xFF0C9B7E),
    auroraText: Color(0xFF087560),
    nebula: Color(0xFF6C5CE7),
    nebulaText: Color(0xFF5B4ED1),
    hydrogen: Color(0xFF1668B3),
    molten: Color(0xFFA66F14),
    moltenText: Color(0xFF8F5F0F),
    nova: Color(0xFFC3272B),
    onAurora: Color(0xFF131629),
    onNebula: Color(0xFF131629),
    onHydrogen: Color(0xFFF6F7FC),
    onMolten: Color(0xFF131629),
    onNova: Color(0xFFF6F7FC),
    chipsSelectedBg: Color(0xFFE2F3F0),
    aiContainerBg: Color(0xFFEAE8FC),
    errorWashBg: Color(0xFFF9E9EA),
    runningWashBg: Color(0xFFE2F3F0),
    alertWashBg: Color(0xFFE2F3F0),
    galaxyStop0: Color(0xFF0C9B7E),
    galaxyStop1: Color(0xFF6C5CE7),
    galaxyStop2: Color(0xFF1668B3),
  );

  /// 夜档（深空基调，主战场）。
  static const AstroPalette dark = AstroPalette(
    bg: Color(0xFF05070F),
    sunken: Color(0xFF0A0D18),
    card: Color(0xFF10131F),
    container: Color(0xFF171B2C),
    cardRaised: Color(0xFF171B2C),
    containerPressed: Color(0xFF1F2438),
    faint: Color(0xFF222741),
    ink900: Color(0xFFEDF0FB),
    ink600: Color(0xFF9AA1C0),
    ink400: Color(0xFF858CB1),
    stroke: Color(0xFF2A2F4D),
    strokeFocus: Color(0xFF3A4066),
    aurora: Color(0xFF4EE0C0),
    auroraText: Color(0xFF4EE0C0),
    nebula: Color(0xFF8B7CF6),
    nebulaText: Color(0xFF8B7CF6),
    hydrogen: Color(0xFF4FC3F7),
    molten: Color(0xFFFFB74D),
    moltenText: Color(0xFFFFB74D),
    nova: Color(0xFFFF5648),
    onAurora: Color(0xFF05070F),
    onNebula: Color(0xFF05070F),
    onHydrogen: Color(0xFF05070F),
    onMolten: Color(0xFF05070F),
    onNova: Color(0xFF05070F),
    chipsSelectedBg: Color(0xFF172C32),
    aiContainerBg: Color(0xFF21223D),
    errorWashBg: Color(0xFF281A23),
    runningWashBg: Color(0xFF141F29),
    alertWashBg: Color(0xFF15232C),
    galaxyStop0: Color(0xFF4EE0C0),
    galaxyStop1: Color(0xFF8B7CF6),
    galaxyStop2: Color(0xFF4FC3F7),
  );
}

/// 全字段 lerp：主题切换 250ms 过渡（§1.5 TWEEN_THEME；经 LocalAstroPalette
/// 下发时组件零改动获得同步过渡）。边界 t<=0/t>=1 直接返回端点实例。
AstroPalette lerpPalette(AstroPalette a, AstroPalette b, double t) {
  if (t <= 0) return a;
  if (t >= 1) return b;
  return AstroPalette(
    bg: Color.lerp(a.bg, b.bg, t)!,
    sunken: Color.lerp(a.sunken, b.sunken, t)!,
    card: Color.lerp(a.card, b.card, t)!,
    container: Color.lerp(a.container, b.container, t)!,
    cardRaised: Color.lerp(a.cardRaised, b.cardRaised, t)!,
    containerPressed: Color.lerp(a.containerPressed, b.containerPressed, t)!,
    faint: Color.lerp(a.faint, b.faint, t)!,
    ink900: Color.lerp(a.ink900, b.ink900, t)!,
    ink600: Color.lerp(a.ink600, b.ink600, t)!,
    ink400: Color.lerp(a.ink400, b.ink400, t)!,
    stroke: Color.lerp(a.stroke, b.stroke, t)!,
    strokeFocus: Color.lerp(a.strokeFocus, b.strokeFocus, t)!,
    aurora: Color.lerp(a.aurora, b.aurora, t)!,
    auroraText: Color.lerp(a.auroraText, b.auroraText, t)!,
    nebula: Color.lerp(a.nebula, b.nebula, t)!,
    nebulaText: Color.lerp(a.nebulaText, b.nebulaText, t)!,
    hydrogen: Color.lerp(a.hydrogen, b.hydrogen, t)!,
    molten: Color.lerp(a.molten, b.molten, t)!,
    moltenText: Color.lerp(a.moltenText, b.moltenText, t)!,
    nova: Color.lerp(a.nova, b.nova, t)!,
    onAurora: Color.lerp(a.onAurora, b.onAurora, t)!,
    onNebula: Color.lerp(a.onNebula, b.onNebula, t)!,
    onHydrogen: Color.lerp(a.onHydrogen, b.onHydrogen, t)!,
    onMolten: Color.lerp(a.onMolten, b.onMolten, t)!,
    onNova: Color.lerp(a.onNova, b.onNova, t)!,
    chipsSelectedBg: Color.lerp(a.chipsSelectedBg, b.chipsSelectedBg, t)!,
    aiContainerBg: Color.lerp(a.aiContainerBg, b.aiContainerBg, t)!,
    errorWashBg: Color.lerp(a.errorWashBg, b.errorWashBg, t)!,
    runningWashBg: Color.lerp(a.runningWashBg, b.runningWashBg, t)!,
    alertWashBg: Color.lerp(a.alertWashBg, b.alertWashBg, t)!,
    galaxyStop0: Color.lerp(a.galaxyStop0, b.galaxyStop0, t)!,
    galaxyStop1: Color.lerp(a.galaxyStop1, b.galaxyStop1, t)!,
    galaxyStop2: Color.lerp(a.galaxyStop2, b.galaxyStop2, t)!,
  );
}

/// 圆角四档（禁自造第五档）。
abstract final class AstroRadius {
  static const double pill = 999.0;
  static const double lg = 20.0;
  static const double md = 16.0;
  static const double sm = 12.0;
}

/// 间距（基数 4）。
abstract final class AstroSpace {
  static const double window = 20.0;
  static const double card = 16.0;
  static const double gap = 8.0;
  static const double gapLg = 12.0;
  static const double section = 24.0;
  static const double sectionLg = 32.0;
  static const double empty = 96.0;
}

/// 字阶一步（size/height 为 dp；kpi 为 mono+tabular 仪表数字）。
class AstroTypeStep {
  const AstroTypeStep({required this.size, required this.height,
      required this.weight, this.mono = false, this.tabular = false});

  final double size;
  final double height;
  final FontWeight weight;
  final bool mono;
  final bool tabular;
}

/// 字阶（正文跟随系统 CJK；数字一律 mono+tabular——「仪表感」）。
abstract final class AstroType {
  static const AstroTypeStep display = AstroTypeStep(size: 32.0, height: 40.0, weight: FontWeight.w600);
  static const AstroTypeStep h1 = AstroTypeStep(size: 24.0, height: 32.0, weight: FontWeight.w600);
  static const AstroTypeStep h2 = AstroTypeStep(size: 20.0, height: 28.0, weight: FontWeight.w500);
  static const AstroTypeStep title = AstroTypeStep(size: 17.0, height: 24.0, weight: FontWeight.w500);
  static const AstroTypeStep titleSm = AstroTypeStep(size: 15.0, height: 22.0, weight: FontWeight.w500);
  static const AstroTypeStep body = AstroTypeStep(size: 14.0, height: 22.0, weight: FontWeight.w400);
  static const AstroTypeStep bodySm = AstroTypeStep(size: 13.0, height: 20.0, weight: FontWeight.w400);
  static const AstroTypeStep caption = AstroTypeStep(size: 12.0, height: 18.0, weight: FontWeight.w400);
  static const AstroTypeStep label = AstroTypeStep(size: 11.0, height: 16.0, weight: FontWeight.w500);
  static const AstroTypeStep kpi = AstroTypeStep(size: 28.0, height: 34.0, weight: FontWeight.w500, mono: true, tabular: true);
  static const String monoFamily = 'JetBrainsMono';
}

/// 动效参数（§1.4 全局唯六，禁自造曲线）。
typedef AstroSpring = ({double stiffness, double damping});

abstract final class AstroMotion {
  static const AstroSpring springPress = (stiffness: 400.0, damping: 0.62);
  static const AstroSpring springSoft = (stiffness: 260.0, damping: 0.85);
  static const AstroSpring springPop = (stiffness: 320.0, damping: 0.72);
  static const int tweenColorMs = 150;
  static const int tweenMoveMs = 250;
  static const int tweenThemeMs = 250;
  static const Curve tweenEasing = Curves.fastOutSlowIn;
  static const int staggerPerItemMs = 30;
  static const int feedbackMaxMs = 300;
}

/// 银河渐变（白名单位 3 处，同屏 ≤1，面积 ≤6%；停驻 0%/52%/100%）。
abstract final class AstroGalaxy {
  static const List<double> positions = [0.0, 0.52, 1.0];
  static const List<Color> darkStops = [Color(0xFF4EE0C0), Color(0xFF8B7CF6), Color(0xFF4FC3F7)];
  static const List<Color> lightStops = [Color(0xFF0C9B7E), Color(0xFF6C5CE7), Color(0xFF1668B3)];
}

/// 星野参数（坐标见 config/design/starfield/seed.json，预生成禁每帧随机）。
abstract final class AstroStarfield {
  static const List<double> alphaSteps = [0.04, 0.08, 0.12];
  static const List<double> sizeSteps = [1.0, 1.5, 2.0];
  static const int densityMin = 60;
  static const int densityMax = 90;
  static const double driftDp = 2.0;
  static const double driftPeriodS = 4.0;
  static const int meteorIntervalS = 120;
  static const int meteorDurationMs = 250;
}

/// 交互参数（§1.7 三端唯一取值处）。
abstract final class AstroInteraction {
  static const double hitMinDp = 40.0;
  static const double sheetDismissDistanceDp = 96.0;
  static const double sheetDismissVelocityDps = 1000.0;
  static const double drawerOpenDistanceRatio = 0.4;
  static const double drawerOpenVelocityDps = 800.0;
  static const int longPressMs = 400;
  static const double slopDp = 8.0;
  static const double swipeConfirmRatio = 0.8;
  static const int navDebounceMs = 30;
  static const int paletteDebounceMs = 150;
}

/// 星符表（icons.yaml；文本内嵌星符一律取自此处，禁散落硬编码）。
abstract final class AstroIcons {
  static const String navHome = '✦';
  static const String navSpider = '☄';
  static const String navParser = '◈';
  static const String navConverter = '❖';
  static const String navPipeline = '✺';
  static const String navMonitor = '◉';
  static const String navHistory = '☾';
  static const String navSettings = '✜';
  static const String navTask = '✧';
  static const String aiIdle = '✵';
  static const String aiThinking = '✶';
  static const String aiThinkingF2 = '✷';
  static const String aiThinkingF3 = '✸';
  static const String aiDone = '☄';
  static const String aiSend = '✵';
  static const String aiFallback = '✧';
  static const String statusOk = '●';
  static const String statusIdle = '◌';
  static const String statusError = '✕';
  static const String statusWarn = '▲';
  static const String statusHint = '✧';
  static const String taskRunning = '◈';
  static const String taskRunningF2 = '◉';
  static const String taskPending = '○';
  static const String taskSuccess = '✓';
  static const String taskFailed = '✕';
  static const String taskCanceled = '⊘';
  static const String miscMeteor = '☄';
  static const String miscStarRank1 = '✦';
  static const String miscStarRank2 = '✦✦';
  static const String miscStarRank3 = '✧';
  static const String miscBinaryStar = '✦✧';
}

/// 主题工厂（替代 theme.dart；夜档零投影、层级靠明度——规格 §二/§六）。
class AstroTheme {
  AstroTheme._();

  static ThemeData light() => _build(AstroPalette.light, Brightness.light);

  static ThemeData dark() => _build(AstroPalette.dark, Brightness.dark);

  static ThemeData _build(AstroPalette p, Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    final scheme = ColorScheme(
      brightness: brightness,
      primary: p.aurora,
      onPrimary: p.onAurora,
      primaryContainer: p.chipsSelectedBg,
      onPrimaryContainer: isDark ? p.aurora : p.auroraText,
      secondary: p.nebula,
      onSecondary: p.onNebula,
      secondaryContainer: p.aiContainerBg,
      onSecondaryContainer: isDark ? p.nebula : p.nebulaText,
      tertiary: p.hydrogen,
      onTertiary: p.onHydrogen,
      error: p.nova,
      onError: p.onNova,
      errorContainer: p.errorWashBg,
      onErrorContainer: p.nova,
      surface: p.card,
      onSurface: p.ink900,
      onSurfaceVariant: p.ink600,
      surfaceContainerLowest: p.bg,
      surfaceContainerLow: p.card,
      surfaceContainer: p.container,
      surfaceContainerHigh: p.cardRaised,
      surfaceContainerHighest: p.containerPressed,
      outline: p.stroke,
      outlineVariant: p.faint,
      shadow: const Color(0x00000000),
      scrim: p.bg.withAlpha(179), // bg@70%（弹层 scrim）
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: p.bg,
      // 夜档零投影：组件级 elevation 恒 0（card 等），层级靠明度不靠描边/投影
      cardTheme: CardThemeData(
        elevation: 0,
        color: p.card,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.md)),
      ),
      dividerTheme: DividerThemeData(
        color: p.faint.withAlpha(179), // faint 仅表格行分隔 @70%
        thickness: 1.0,
        space: 1.0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: p.sunken,
        isDense: true,
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm),
          borderSide: BorderSide(color: p.stroke, width: 1.0),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm),
          borderSide: BorderSide(color: p.aurora, width: 1.5), // 焦点=aurora 1.5dp
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm),
          borderSide: BorderSide(color: p.nova, width: 1.5),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm),
          borderSide: BorderSide(color: p.nova, width: 1.5),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: p.bg,
        useIndicator: true,
        indicatorColor: p.aurora,
        indicatorShape: const StadiumBorder(),
        selectedIconTheme: IconThemeData(color: p.onAurora),
        unselectedIconTheme: IconThemeData(color: p.ink600),
        selectedLabelTextStyle: TextStyle(color: p.ink900, fontWeight: FontWeight.w600),
        unselectedLabelTextStyle: TextStyle(color: p.ink600),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: p.container,
        selectedColor: p.chipsSelectedBg,
        side: BorderSide(color: p.stroke),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.pill)),
        labelStyle: TextStyle(color: p.ink900),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: p.cardRaised,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.lg)),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: p.ink900,
        unselectedLabelColor: p.ink600,
        indicatorColor: p.aurora,
        dividerColor: Colors.transparent,
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: p.cardRaised,
          borderRadius: BorderRadius.circular(AstroRadius.sm)),
        textStyle: TextStyle(color: p.ink900, fontSize: AstroType.caption.size),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: p.cardRaised,
        contentTextStyle: TextStyle(color: p.ink900),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm)),
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: p.cardRaised,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AstroRadius.sm)),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStatePropertyAll(p.onAurora),
        trackColor: WidgetStatePropertyAll(p.chipsSelectedBg),
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStatePropertyAll(p.aurora),
        checkColor: WidgetStatePropertyAll(p.onAurora),
        side: BorderSide(color: p.stroke),
      ),
    );
  }
}
