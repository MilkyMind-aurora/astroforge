import 'package:flutter/material.dart';

/// 星伴 AI 抽屉（方案 3.10 对应 TUI Ctrl+Shift+A 面板）。
/// 流式回复（/ws/ai 的 ai_delta）与指令卡片属 Phase 9.6。
class AiDrawer extends StatelessWidget {
  const AiDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = TextEditingController();
    return Drawer(
      width: 380,
      child: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const Text('✦ 星伴 AI', style: TextStyle(fontSize: 16)),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            const Expanded(
              child: Center(
                child: Text(
                  '本地 GGUF 引擎对接属 Phase 9.6：\n流式气泡 · 指令卡片 · 历史会话',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(12),
              child: TextField(
                controller: controller,
                decoration: const InputDecoration(
                  hintText: '输入指令（引擎对接后生效）',
                  suffixIcon: Icon(Icons.send_outlined),
                ),
                onSubmitted: (_) => controller.clear(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
