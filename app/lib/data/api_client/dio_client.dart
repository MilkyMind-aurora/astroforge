import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config.dart';

/// 服务核心统一信封：{"code":0,"message":"ok","data":...}
class ApiError implements Exception {
  ApiError(this.code, this.message);

  final int code;
  final String message;

  @override
  String toString() => '[$code] $message';
}

class ApiClient {
  ApiClient() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = AppConfig.resolveToken();
          if (token != null) options.headers['X-AstroForge-Token'] = token;
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio = Dio(BaseOptions(
    baseUrl: AppConfig.serviceBaseUrl,
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 15),
  ));

  dynamic _unwrap(Response resp) {
    final body = resp.data;
    if (body is! Map || !body.containsKey('code')) return body;
    final code = body['code'] as int;
    if (code == 0) return body['data'];
    throw ApiError(code, (body['message'] ?? 'unknown') as String);
  }

  Future<Map<String, dynamic>> health() async {
    try {
      final data = _unwrap(await _dio.get('/api/v1/system/health'));
      return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
    } on DioException catch (e) {
      throw ApiError(-1, '服务不可达：${e.message}');
    }
  }

  Future<Map<String, dynamic>> envCheck() async {
    final data = _unwrap(await _dio.get('/api/v1/system/env-check'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  Future<List<dynamic>> listTasks({int page = 1, String? status}) async {
    final data = _unwrap(await _dio.get('/api/v1/tasks', queryParameters: {
      'page': page,
      'status': ?status,
    }));
    if (data is Map && data['items'] is List) return data['items'] as List<dynamic>;
    return const [];
  }

  /// 创建任务（独立调用模式）：taskType 如 spider_single / mineru / md2docx。
  Future<Map<String, dynamic>> createTask(
    String taskType,
    Map<String, dynamic> config, {
    String? title,
  }) async {
    final data = _unwrap(await _dio.post('/api/v1/tasks', data: {
      'task_type': taskType,
      'config': config,
      'title': ?title,
      'mode': 'standalone',
    }));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 取消任务。
  Future<void> cancelTask(String taskUuid) async {
    await _dio.post('/api/v1/tasks/$taskUuid/cancel');
  }

  /// 任务详情（含 steps 步骤明细——时间线/续跑数据源）。
  Future<Map<String, dynamic>> taskDetail(String taskUuid) async {
    final data = _unwrap(await _dio.get('/api/v1/tasks/$taskUuid'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 重试失败/取消的任务（新建同配置任务）。
  Future<Map<String, dynamic>> retryTask(String taskUuid) async {
    final data = _unwrap(await _dio.post('/api/v1/tasks/$taskUuid/retry'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 步骤级续跑（MF3.5 API：POST /tasks/{uuid}/steps/{index}/retry）。
  /// 仅 failed/canceled 任务的失败或未运行步骤可续跑；返回体 task_uuid
  /// 不变（原地更新，不裂成两条）。
  Future<Map<String, dynamic>> retryTaskStep(String taskUuid, int stepIndex) async {
    final data =
        _unwrap(await _dio.post('/api/v1/tasks/$taskUuid/steps/$stepIndex/retry'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 任务日志（REST 补拉：WS 断线/面板初始化）。
  Future<Map<String, dynamic>> taskLogs(String taskUuid, {int offset = 0}) async {
    final data = _unwrap(await _dio.get('/api/v1/tasks/$taskUuid/logs',
        queryParameters: {
      'offset': offset,
    }));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 监控历史回放（range: 1h|6h|24h；实时数据走 /ws/monitor）。
  Future<Map<String, dynamic>> monitorHistory(String range) async {
    final data = _unwrap(await _dio.get('/api/v1/monitor/history',
        queryParameters: {
      'range': range,
    }));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// DOCX 模板列表（任务页模板选择数据源）。
  Future<Map<String, dynamic>> listTemplates() async {
    final data = _unwrap(await _dio.get('/api/v1/templates'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  // ---- NovaFlow 流水线（Phase 5）----
  Future<List<dynamic>> listPipelines() async {
    final data = _unwrap(await _dio.get('/api/v1/pipelines'));
    if (data is Map && data['items'] is List) return data['items'] as List<dynamic>;
    return const [];
  }

  Future<Map<String, dynamic>> runPipeline(String name,
      {Map<String, dynamic>? params, String? title}) async {
    final data = _unwrap(await _dio.post('/api/v1/pipelines/$name/run', data: {
      'params': params ?? <String, dynamic>{},
      'title': ?title,
    }));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> savePipeline(String yamlContent) async {
    final data = _unwrap(
        await _dio.post('/api/v1/pipelines', data: {'yaml_content': yamlContent}));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 设置中心（Phase 1.3.3）：配置摘要 + 覆盖设置。
  Future<Map<String, dynamic>> configSummary() async {
    final data = _unwrap(await _dio.get('/api/v1/system/config-summary'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> listAppSettings() async {
    final data = _unwrap(await _dio.get('/api/v1/app-settings'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  Future<void> setAppSetting(String key, Object value) async {
    await _dio.put('/api/v1/app-settings/$key', data: {'value': value});
  }

  Future<void> resetToken() async {
    await _dio.post('/api/v1/service/token/reset');
  }

  // ---- 星伴 AI（方案 §5.2/§5.6，MF4）----

  /// 引擎状态探测（服务端只探测不拉起——watcher.probe_status）。
  /// reachable=true 时随引擎 /v1/health 返回 current_model 等字段。
  Future<Map<String, dynamic>> engineStatus() async {
    final data = _unwrap(await _dio.get('/api/v1/ai/engine/status'));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 模型热切换两档（服务端白名单：qwen2b / ornith9b），首载 9B 耗时较长。
  Future<Map<String, dynamic>> switchModel(String modelKey) async {
    final data = _unwrap(
        await _dio.post('/api/v1/ai/model/switch', data: {'model_key': modelKey}));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }

  /// 指令对话（REST 一问一答；服务端在 instruction 命中时直接建任务并回
  /// task_uuid——已实现 API 为准，客户端不做二次「确认创建」）。
  Future<Map<String, dynamic>> aiChat(String message, {int? conversationId}) async {
    final data = _unwrap(await _dio.post('/api/v1/ai/chat', data: {
      'message': message,
      'conversation_id': ?conversationId,
    }));
    return (data ?? <String, dynamic>{}) as Map<String, dynamic>;
  }
}

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
