import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_providers.dart';
import '../../core/design/design.dart';

/// 重连横幅（#20 挤压进场，方案 §5.1/§1.8）：WS 断连 → 横幅从顶挤下、
/// 内容下移让位（AnimatedSize 高度 0→banner）；恢复自动滑出。
/// 冷启动期（尚未连上过）不弹——连接引导由首页 REST 分支负责。
class DisconnectBanner extends ConsumerWidget {
  const DisconnectBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final palette = AstroPaletteScope.of(context);
    final state = ref.watch(connectionProvider);
    final visible = state.bannerVisible;
    return ClipRect(
      child: AnimatedSize(
        duration: const Duration(milliseconds: 300), // dur-medium（280~400ms 档）
        curve: Curves.fastOutSlowIn,
        alignment: Alignment.topCenter,
        child: visible
            ? Material(
                color: palette.errorWashBg,
                child: InkWell(
                  onTap: () =>
                      ref.read(connectionProvider.notifier).nudgeReconnect(),
                  child: SizedBox(
                    width: double.infinity,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          vertical: 8, horizontal: AstroSpace.window),
                      child: Row(
                        children: [
                          Text(
                            AstroIcons.statusIdle,
                            style: TextStyle(color: palette.nova, fontSize: 12),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              '服务核心连接断开 · 重连中（点击立即重试）',
                              style: TextStyle(
                                fontSize: AstroType.bodySm.size,
                                color: palette.ink900,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              )
            : const SizedBox(width: double.infinity),
      ),
    );
  }
}
