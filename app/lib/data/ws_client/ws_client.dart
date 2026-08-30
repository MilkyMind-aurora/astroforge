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

  ValueListenable<WsStatus> get status => _status;
  Stream<Map<String, dynamic>> get messages => _messages.stream;

  void connect() {
    if (_disposed) return;
    _status.value = WsStatus.connecting;
    final token = AppConfig.resolveToken() ?? '';
    final uri = Uri.parse(
      '${AppConfig.serviceBaseUrl.replaceAll('http', 'ws')}$path?token=$token',
    );
    try {
      _channel = WebSocketChannel.connect(uri);
      _channel!.stream.listen(
        _onData,
        onDone: _onDone,
        onError: (_) => _onDone(),
        cancelOnError: true,
      );
      _status.value = WsStatus.connected;
      _retryCount = 0;
      _resetHeartbeat();
    } catch (e) {
      developer.log('WS connect failed: $e', name: 'ForgeWebSocket');
      _scheduleRetry();
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
    _retryTimer = Timer(delay, connect);
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
