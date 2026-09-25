// MF5 纯逻辑单测：任务 schema 契约（§5.5 基线）/ URL 客户端预检
// （服务 url_guard 同族语义）/ 拖拽扩展名映射 / 监控滚动窗口 / 状态视觉映射。
import 'package:astroforge/core/app_providers.dart';
import 'package:astroforge/data/task_schema.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('taskSchema（§5.5 数据契约）', () {
    test('task_type 枚举与服务核心 MODULE_MAP 同源（8 型）', () {
      final expected = {
        'spider_single', 'spider_site', 'spider_pdf', 'spider_table',
        'mineru', 'wpd', 'anydoc', 'md2docx',
      };
      expect(taskSchema.map((t) => t.type).toSet(), expected);
    });

    test('表单不含服务端注入键（browser/mineru max_threads 禁出现）', () {
      for (final spec in taskSchema) {
        for (final field in spec.fields) {
          expect(field.key, isNot('browser'));
          expect(field.key, isNot('max_threads'));
        }
      }
    });

    test('spider_table 置灰（Phase 2 开发中 · 服务端 3006）', () {
      final table = taskSchema.firstWhere((t) => t.type == 'spider_table');
      expect(table.deprecated, isTrue);
    });

    test('md2docx 模板字段默认 tech_doc（模块 CLI 缺省同源）', () {
      final md2docx = taskSchema.firstWhere((t) => t.type == 'md2docx');
      final template =
          md2docx.fields.firstWhere((f) => f.key == 'template');
      expect(template.defaultValue, 'tech_doc');
    });
  });

  group('validateExternalUrl（外联校验仅 http/https，拒绝本机/私有/保留）', () {
    test('合法公网 URL 通过', () {
      expect(validateExternalUrl('https://cn.vuejs.org/guide/intro.html'), isNull);
      expect(validateExternalUrl('http://example.com'), isNull);
    });

    test('拒绝非 http/https 协议', () {
      expect(validateExternalUrl('ftp://example.com'), isNotNull);
      expect(validateExternalUrl('file:///etc/passwd'), isNotNull);
    });

    test('拒绝 localhost 与 .local 域名', () {
      expect(validateExternalUrl('http://localhost:8420'), isNotNull);
      expect(validateExternalUrl('http://mine.local/x'), isNotNull);
    });

    test('拒绝环回/私有/保留 IP 段', () {
      expect(validateExternalUrl('http://127.0.0.1:8420'), isNotNull);
      expect(validateExternalUrl('http://10.1.2.3'), isNotNull);
      expect(validateExternalUrl('http://172.16.0.9'), isNotNull);
      expect(validateExternalUrl('http://192.168.1.1'), isNotNull);
      expect(validateExternalUrl('http://169.254.1.1'), isNotNull);
      expect(validateExternalUrl('http://0.0.0.0'), isNotNull);
    });

    test('公网 IP 放行、空串拒绝', () {
      expect(validateExternalUrl('https://8.8.8.8/dns-query'), isNull);
      expect(validateExternalUrl(''), isNotNull);
      expect(validateExternalUrl('not-a-url'), isNotNull);
    });
  });

  group('dropTargetForExtension（拖拽扩展名映射）', () {
    test('§5.2 映射：pdf→mineru / office→anydoc / md→md2docx', () {
      expect(dropTargetForExtension('.pdf')!.$1, 'mineru');
      expect(dropTargetForExtension('.docx')!.$1, 'anydoc');
      expect(dropTargetForExtension('.xlsx')!.$1, 'anydoc');
      expect(dropTargetForExtension('.md')!.$1, 'md2docx');
    });

    test('未命中扩展名返回 null（禁硬造任务）', () {
      expect(dropTargetForExtension('.exe'), isNull);
      expect(dropTargetForExtension('.png'), isNull);
    });
  });

  group('MonitorWindow（/ws/monitor 60 点滚动窗口）', () {
    test('push 逐点入窗并在 60 处封顶', () {
      var window = const MonitorWindow();
      for (var i = 0; i < 65; i++) {
        window = window.push(MonitorSample(
          cpuPercent: i.toDouble(),
          memUsedGb: 8,
          memPercent: 50,
          diskMbps: 0,
          activeProcesses: 1,
        ));
      }
      expect(window.cpu.length, MonitorWindow.windowSize);
      // 先进先出：最早两点已被挤出
      expect(window.cpu.first, 5.0);
      expect(window.cpu.last, 64.0);
      expect(window.latest?.cpuPercent, 64.0);
    });
  });
}
