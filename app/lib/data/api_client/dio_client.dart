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

  /// 重试失败/取消的任务（新建同配置任务）。
  Future<Map<String, dynamic>> retryTask(String taskUuid) async {
    final data = _unwrap(await _dio.post('/api/v1/tasks/$taskUuid/retry'));
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
}

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
