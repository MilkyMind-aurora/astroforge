import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/config.dart';

/// WS 连接状态（方案 3.10 断线策略）。
enum WsStatus { connecting, connected, disconnected }

/// 通用 WebSocket 客户端：指数退避重连（1s→60s 封顶）+ 45s 心跳超时。
/// 消息信封：{"type","payload","ts"}，服务端 30s 心跳，45s 未收到即重连。
/// 重连成功后由消费方 REST 全量刷新（pro §2.4：杜绝「僵尸状态」）。
class ForgeWebSocket {
  ForgeWebSocket({required this.path});

  final String path;
  final _status = ValueNotifier<WsStatus>(WsStatus.disconnected);
  final _messages = StreamController<Map<String, dynamic>>.broadcast();

  WebSocketChannel? _channel;
  Timer? _retryTimer;
  Timer? _heartbeatTimer;
  int _retryCount = 0;
  bool _disposed = false;
  bool _connecting = false;

  ValueListenable<WsStatus> get status => _status;
  Stream<Map<String, dynamic>> get messages => _messages.stream;

  /// 发送 JSON 消息（仅握手完成态；未连接静默丢弃，由调用方决定降级回执）。
  void send(Map<String, dynamic> payload) {
    final channel = _channel;
    if (channel == null || _status.value != WsStatus.connected) return;
    channel.sink.add(jsonEncode(payload));
  }

  Future<void> connect() async {
    if (_disposed || _connecting) return;
    _connecting = true;
    _status.value = WsStatus.connecting;
    final token = AppConfig.resolveToken() ?? '';
    final uri = Uri.parse(
      '${AppConfig.serviceBaseUrl.replaceAll('http', 'ws')}$path?token=$token',
    );
    final channel = WebSocketChannel.connect(uri);
    _channel = channel;
    try {
      // 握手完成才置 connected（旧实现乐观置位，断连横幅会误判）
      await channel.ready;
      if (_disposed) return;
      _status.value = WsStatus.connected;
      _retryCount = 0;
      _resetHeartbeat();
      channel.stream.listen(
        _onData,
        onDone: _onDone,
        onError: (_) => _onDone(),
        cancelOnError: true,
      );
    } catch (e) {
      developer.log('WS connect failed: $e', name: 'ForgeWebSocket');
      _scheduleRetry();
    } finally {
      _connecting = false;
    }
  }

  void _onData(dynamic raw) {
    _resetHeartbeat();
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      if (msg['type'] == 'heartbeat') return;
      _messages.add(msg);
    } catch (_) {/* 非 JSON 帧忽略 */}
  }

  void _onDone() {
    if (_disposed) return;
    _status.value = WsStatus.disconnected;
    _heartbeatTimer?.cancel();
    _scheduleRetry();
  }

  void _resetHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer(const Duration(seconds: 45), () {
      // 45s 未收到任何帧：主动断开触发重连（方案补丁 7）
      _channel?.sink.close();
      _onDone();
    });
  }

  void _scheduleRetry() {
    if (_disposed) return;
    final delay = Duration(seconds: (1 << _retryCount).clamp(1, 60));
    _retryCount++;
    _retryTimer?.cancel();
    _retryTimer = Timer(delay, () => unawaited(connect()));
  }

  void dispose() {
    _disposed = true;
    _retryTimer?.cancel();
    _heartbeatTimer?.cancel();
    _channel?.sink.close();
    _messages.close();
    _status.dispose();
  }
}
