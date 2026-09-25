import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client/dio_client.dart';
import '../data/ws_client/ws_client.dart';

/// 壳层级运行时状态（MF4）：
/// ① monitor WS 连接态（断连挤压横幅 #20 的唯一驱动）；
/// ② env-check 体检（轨底健康点 + 首页 9/9 胶囊）；
/// ③ 页面/任务事件总线（history 轮询改 WS 消费后的刷新信号）。

// ---- ① 连接态（/ws/monitor 常驻单例）----

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
      ..status.addListener(_onStatus);
    unawaited(_ws.connect());
  }

  late final ForgeWebSocket _ws;

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
const railHealthEnvKeys = <int, String>{
  1: 'Chromium', // 采集
  2: 'MinerU', // 解析
  3: 'anydoc', // 转换
  4: 'Conda', // 流水线
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
