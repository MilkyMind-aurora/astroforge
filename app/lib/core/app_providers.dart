import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/api_client/dio_client.dart';
import '../data/ws_client/ws_client.dart';

/// 壳层级运行时状态（MF4）：
/// ① monitor WS 连接态（断连挤压横幅 #20 的唯一驱动）；
/// ② env-check 体检（轨底健康点 + 首页 9/9 胶囊）；
/// ③ 页面/任务事件总线（history 轮询改 WS 消费后的刷新信号）。

// ---- ① 连接态（/ws/monitor 常驻单例）----

/// 单次监控采样（服务 memory_monitor.sample 字段：CPU%/内存GB/内存%/磁盘读写）。
class MonitorSample {
  const MonitorSample({
    required this.cpuPercent,
    required this.memUsedGb,
    required this.memPercent,
    required this.diskMbps,
    required this.activeProcesses,
  });

  final double cpuPercent;
  final double memUsedGb;
  final double memPercent;
  final double diskMbps; // 读+写合计 MB/s
  final int activeProcesses;
}

/// 实时滚动窗口（60 点 ×1s，方案 §5.3 Sparkline 窗口）。
/// 不可变实例整体替换（1s 一次，watch 方零 diff 成本）。
class MonitorWindow {
  const MonitorWindow({
    this.cpu = const [],
    this.mem = const [],
    this.disk = const [],
    this.latest,
  });

  final List<double> cpu;
  final List<double> mem;
  final List<double> disk;
  final MonitorSample? latest;

  static const int windowSize = 60;

  MonitorWindow push(MonitorSample sample) {
    List<double> push(List<double> src, double value) {
      final next = [...src, value];
      if (next.length > windowSize) next.removeRange(0, next.length - windowSize);
      return next;
    }

    return MonitorWindow(
      cpu: push(cpu, sample.cpuPercent),
      mem: push(mem, sample.memPercent),
      disk: push(disk, sample.diskMbps),
      latest: sample,
    );
  }
}

class ConnectionState {
  const ConnectionState({
    required this.status,
    required this.hasConnectedOnce,
  });

  final WsStatus status;

  /// 是否成功连上过至少一次：冷启动期（尚未连上）不弹横幅，
  /// 连接引导由首页 REST 探活分支负责（§5.1 壳内嵌态）。
  final bool hasConnectedOnce;

  bool get bannerVisible =>
      hasConnectedOnce && status != WsStatus.connected;
}

class ConnectionController extends StateNotifier<ConnectionState> {
  ConnectionController() : super(const ConnectionState(
          status: WsStatus.disconnected, hasConnectedOnce: false)) {
    _ws = ForgeWebSocket(path: '/ws/monitor')
      ..status.addListener(_onStatus)
      // 监控采样入滚动窗口（仪表胶囊 + 监控弹层实时数据源，IA 裁决：
      // 监控降级为右上胶囊+弹层后 /ws/monitor 由壳层常驻消费）
      ..messages.listen(_onMonitorMessage);
    unawaited(_ws.connect());
  }

  late final ForgeWebSocket _ws;

  /// 实时窗口（不可变实例整体替换）。
  final monitorWindow = ValueNotifier<MonitorWindow>(const MonitorWindow());

  void _onMonitorMessage(Map<String, dynamic> envelope) {
    if (envelope['type'] != 'monitor') return;
    final payload = (envelope['payload'] as Map?)?.cast<String, dynamic>();
    if (payload == null) return;
    final sample = MonitorSample(
      cpuPercent: (payload['cpu_percent'] as num?)?.toDouble() ?? 0,
      memUsedGb: (payload['mem_used_gb'] as num?)?.toDouble() ?? 0,
      memPercent: (payload['mem_percent'] as num?)?.toDouble() ?? 0,
      diskMbps: ((payload['disk_read_mbps'] as num?)?.toDouble() ?? 0) +
          ((payload['disk_write_mbps'] as num?)?.toDouble() ?? 0),
      activeProcesses: (payload['active_processes'] as num?)?.toInt() ?? 0,
    );
    monitorWindow.value = monitorWindow.value.push(sample);
  }

  void _onStatus() {
    final status = _ws.status.value;
    if (status == WsStatus.connected && !state.hasConnectedOnce) {
      state = ConnectionState(status: status, hasConnectedOnce: true);
      return;
    }
    state = ConnectionState(
      status: status,
      hasConnectedOnce: state.hasConnectedOnce,
    );
  }

  /// 首页/历史 REST 探活恢复后，主动促发一次 WS 重连（杜绝僵尸状态）。
  void nudgeReconnect() {
    if (_ws.status.value != WsStatus.connected) {
      unawaited(_ws.connect());
    }
  }

  @override
  void dispose() {
    _ws.status.removeListener(_onStatus);
    _ws.dispose();
    monitorWindow.dispose();
    super.dispose();
  }
}

final connectionProvider =
    StateNotifierProvider<ConnectionController, ConnectionState>(
  (ref) => ConnectionController(),
);

// ---- ② env-check 体检 ----

/// env-check 原始返回：{ok_count, total, items:[{name, ok, detail}]}
class EnvCheckController extends AutoDisposeAsyncNotifier<Map<String, dynamic>> {
  @override
  Future<Map<String, dynamic>> build() {
    return ref.read(apiClientProvider).envCheck();
  }

  Future<void> refresh() async {
    state = const AsyncLoading<Map<String, dynamic>>().copyWithPrevious(state);
    state = await AsyncValue.guard(() async {
      final api = ref.read(apiClientProvider);
      return api.envCheck();
    });
  }
}

final envCheckProvider = AsyncNotifierProvider.autoDispose<EnvCheckController,
    Map<String, dynamic>>(EnvCheckController.new);

/// 健康点语义映射（星空设计系统规格 §三.1：ok aurora / 缺失 ink-400 / 异常 nova）。
/// 服务端 env-check 是环境项列表，无模块一一对应键——按名称包含关系映射，
/// 无对应环境项的目的地不显示健康点（禁伪造）。
/// IA 8→5（V1.1-4）后索引：0 首页 / 1 任务 / 2 流水线 / 3 历史 / 4 设置。
/// 「任务」页为采集+解析+转换三合一（模块环境缺失降级由页内体检卡承担，
/// 不伪造单一健康点）；流水线引擎依赖 conda。
const railHealthEnvKeys = <int, String>{
  2: 'Conda', // 流水线
};

enum HealthLevel { ok, missing, error, unknown }

HealthLevel envItemHealth(Map<String, dynamic> item) {
  if (item['ok'] == true) return HealthLevel.ok;
  return HealthLevel.missing;
}

// ---- ③ 事件总线 ----

/// 任务变更事件（REST 建任务/重试/AI 指令卡创建后广播；
/// history 页监听后刷新——替代 5s 轮询的「新任务可见性」信号源之一）。
class TaskEvents extends ChangeNotifier {
  void taskMutated() => notifyListeners();
}

final taskEventsProvider =
    ChangeNotifierProvider<TaskEvents>((ref) => TaskEvents());

/// F5 刷新请求（§5.1 键盘表：stale-while-revalidate；页面自行决定刷新范围）。
class RefreshEvents extends ChangeNotifier {
  void refreshRequested() => notifyListeners();
}

final refreshEventsProvider =
    ChangeNotifierProvider<RefreshEvents>((ref) => RefreshEvents());

/// 拖拽/能力胶囊 → 任务页预填（「去表单精调」非死胡同，UX P1-2）。
/// 载荷：{task_type, config(部分预填), reason}；任务页 initState 消费一次即清。
class TaskPrefill {
  const TaskPrefill({
    required this.taskType,
    this.config = const {},
    this.reason = '',
  });

  final String taskType;
  final Map<String, dynamic> config;
  final String reason;
}

final taskPrefillProvider = StateProvider<TaskPrefill?>((ref) => null);

// ---- ④ 外观开关（设置页外观组；appearance.starfield/mascot 双端同源）----

class AppearanceFlags {
  const AppearanceFlags({
    this.starfield = true,
    this.mascot = true,
  });

  final bool starfield;
  final bool mascot;
}

/// 星野/星仔开关：本地 SharedPreferences 即时生效（含服务不可达场景），
/// 尽力同步服务端 app_settings（appearance.starfield / appearance.mascot，
/// 与 TUI 双端同源——方案 §2.6 / V1-B.6 白名单）。
class AppearanceController extends StateNotifier<AppearanceFlags> {
  AppearanceController() : super(const AppearanceFlags()) {
    _restore();
  }

  static const _starfieldKey = 'appearance.starfield';
  static const _mascotKey = 'appearance.mascot';

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    state = AppearanceFlags(
      starfield: prefs.getBool(_starfieldKey) ?? true,
      mascot: prefs.getBool(_mascotKey) ?? true,
    );
  }

  void _persist(bool starfield, bool mascot) {
    SharedPreferences.getInstance().then((p) {
      p.setBool(_starfieldKey, starfield);
      p.setBool(_mascotKey, mascot);
    });
  }

  /// 尽力同步服务端（app_settings 白名单键；失败静默——本地仍生效）。
  Future<void> _syncServer(String key, bool value) async {
    try {
      await _api?.setAppSetting(key, value);
    } on ApiError {
      // 服务不可达：下次改设置再同步（不阻断本地生效）
    }
  }

  ApiClient? _api;

  /// 由壳层注入 ApiClient（避免构造期依赖 ProviderContainer）。
  void attachApi(ApiClient api) => _api = api;

  void setStarfield(bool value) {
    state = AppearanceFlags(starfield: value, mascot: state.mascot);
    _persist(value, state.mascot);
    _syncServer('appearance.starfield', value);
  }

  void setMascot(bool value) {
    state = AppearanceFlags(starfield: state.starfield, mascot: value);
    _persist(state.starfield, value);
    _syncServer('appearance.mascot', value);
  }
}

final appearanceProvider =
    StateNotifierProvider<AppearanceController, AppearanceFlags>(
  (ref) => AppearanceController(),
);
