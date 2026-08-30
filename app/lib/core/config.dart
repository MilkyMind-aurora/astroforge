import 'dart:io';

/// 客户端自身配置（方案 3.10）。
/// 业务数据一律经服务 API 获取，这里只存连接信息与服务地址。
class AppConfig {
  AppConfig._();

  /// 服务核心地址（Sidereal Core，127.0.0.1:8420）
  static const String serviceBaseUrl = String.fromEnvironment(
    'ASTROFORGE_SERVICE_URL',
    defaultValue: 'http://127.0.0.1:8420',
  );

  /// token 读取优先级：环境变量 ASTROFORGE_SERVICE_TOKEN → 共享 token 文件
  static String? resolveToken() {
    final fromEnv = Platform.environment['ASTROFORGE_SERVICE_TOKEN'];
    if (fromEnv != null && fromEnv.isNotEmpty) return fromEnv;
    final tokenFile = Platform.environment['ASTROFORGE_TOKEN_FILE'] ??
        'data/service_token';
    final file = File(tokenFile);
    if (file.existsSync()) {
      final content = file.readAsStringSync().trim();
      if (content.isNotEmpty) return content;
    }
    return null;
  }
}
