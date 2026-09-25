/// 「任务」页 schema 唯一核对基线（方案 §5.5 数据契约表）：
/// 字段键与模块 CLI 真实消费键一一对应（modules/*/cli.py 实测核对——
/// spider cli.py:24/40-48/57、mineru cli.py:25/33、wpd cli.py:44/48/77/79/103、
/// anydoc cli.py:24/40/46、md2docx cli.py:34/41/43/46）。
/// `browser`（chromium_path/headless/no_sandbox）与 mineru `max_threads` 由
/// 服务端注入，表单不出现这两类键【硬性】。
/// task_type 枚举与服务核心 task_scheduler.MODULE_MAP 同源（8 型）。
library;

/// 表单控件类型（§5.5 控件列）。
enum TaskFieldType {
  /// URL 输入井（外联校验仅 http/https，客户端预检+服务端 url_guard 兜底）。
  url,

  /// 整数步进。
  intNumber,

  /// 小数（秒数等）。
  decimal,

  /// 开关。
  toggle,

  /// 目录选择器（file_picker getDirectoryPath）。
  directory,

  /// 文件选择器（file_picker openFile）。
  file,

  /// 模板选择（数据源 GET /templates；底部弹层见任务页）。
  template,

  /// 文件或目录二选一（wpd：input_path 单图 / input_dir 批量）。
  fileOrDirectory,
}

/// 单字段规格。
class TaskFieldSpec {
  const TaskFieldSpec({
    required this.key,
    required this.label,
    required this.type,
    this.defaultValue,
    this.advanced = false,
    this.hint,
    this.optional = false,
  });

  final String key;
  final String label;
  final TaskFieldType type;
  final Object? defaultValue;

  /// 高级折叠区字段（「✧ 高级」行内展开）。
  final bool advanced;
  final String? hint;

  /// 可选字段（留空即不下发——禁伪造空键）。
  final bool optional;
}

/// 任务类型规格（表单页 ChoiceChip 一项）。
class TaskTypeSpec {
  const TaskTypeSpec({
    required this.type,
    required this.label,
    required this.glyph,
    required this.description,
    required this.fields,
    this.deprecated = false,
  });

  final String type;
  final String label;

  /// 星符（icons.yaml 语义名经 AstroIcons 引用，禁散落字符）。
  final String glyph;
  final String description;
  final List<TaskFieldSpec> fields;

  /// 服务端 3006「Phase 2 开发中」的类型（spider_table）——卡置灰标「开发中」。
  final bool deprecated;
}

/// §5.5 schema 表（唯一核对基线；模块 CLI config 键变更时双端同步改表）。
const taskSchema = <TaskTypeSpec>[
  TaskTypeSpec(
    type: 'spider_single',
    label: '单页转 MD',
    glyph: '☄',
    description: '渲染单个网页并提取正文为 Markdown',
    fields: [
      TaskFieldSpec(key: 'url', label: '目标 URL', type: TaskFieldType.url),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        defaultValue: 'output',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'spider_site',
    label: '整站结构化',
    glyph: '✺',
    description: '解析侧边栏目录，按章节输出 Markdown 树',
    fields: [
      TaskFieldSpec(key: 'url', label: '目标 URL', type: TaskFieldType.url),
      TaskFieldSpec(
        key: 'max_pages',
        label: '最大页面数',
        type: TaskFieldType.intNumber,
        defaultValue: 200,
      ),
      TaskFieldSpec(
        key: 'request_interval',
        label: '请求间隔（秒）',
        type: TaskFieldType.decimal,
        defaultValue: 1.0,
      ),
      TaskFieldSpec(
        key: 'structured',
        label: '结构化输出（按章节目录）',
        type: TaskFieldType.toggle,
        defaultValue: true,
      ),
      TaskFieldSpec(
        key: 'resume',
        label: '断点续爬（跳过已抓页面）',
        type: TaskFieldType.toggle,
        defaultValue: true,
      ),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        defaultValue: 'output/site',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'spider_pdf',
    label: 'PDF 批量',
    glyph: '⬇',
    description: '抓取页面上的全部 PDF 链接并下载',
    fields: [
      TaskFieldSpec(key: 'url', label: '目标 URL', type: TaskFieldType.url),
      TaskFieldSpec(
        key: 'auto_retry',
        label: '失败自动重试次数',
        type: TaskFieldType.intNumber,
        defaultValue: 3,
      ),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        defaultValue: 'output/pdf',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'spider_table',
    label: '表格抓取',
    glyph: '▦',
    description: '批量抓取公开数据表格（Phase 2 开发中）',
    deprecated: true,
    fields: [
      TaskFieldSpec(key: 'url', label: '目标 URL', type: TaskFieldType.url),
    ],
  ),
  TaskTypeSpec(
    type: 'mineru',
    label: '解析 PDF',
    glyph: '◈',
    description: 'MinerU 文档结构化解析（PDF/图片 → Markdown）',
    fields: [
      TaskFieldSpec(key: 'input_path', label: '输入文件', type: TaskFieldType.file),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        hint: '缺省：输入同目录 / mineru_out',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'wpd',
    label: '图表取数',
    glyph: '◈',
    description: 'WebPlotDigitizer 图表数值提取（CSV / 追加 MD）',
    fields: [
      TaskFieldSpec(
        key: 'input_path',
        label: '输入（单图或目录）',
        type: TaskFieldType.fileOrDirectory,
        hint: '单图 = 逐张取数；目录 = 批量',
      ),
      TaskFieldSpec(
        key: 'x_min',
        label: 'X 轴最小值',
        type: TaskFieldType.decimal,
        advanced: true,
        optional: true,
      ),
      TaskFieldSpec(
        key: 'x_max',
        label: 'X 轴最大值',
        type: TaskFieldType.decimal,
        advanced: true,
        optional: true,
      ),
      TaskFieldSpec(
        key: 'y_min',
        label: 'Y 轴最小值',
        type: TaskFieldType.decimal,
        advanced: true,
        optional: true,
      ),
      TaskFieldSpec(
        key: 'y_max',
        label: 'Y 轴最大值',
        type: TaskFieldType.decimal,
        advanced: true,
        optional: true,
      ),
      TaskFieldSpec(
        key: 'append_to_md',
        label: '追加到同目录 Markdown',
        type: TaskFieldType.toggle,
        defaultValue: false,
      ),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        hint: '缺省：输入同目录 / wpd_out',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'anydoc',
    label: '入库 Office→MD',
    glyph: '❖',
    description: 'anydoc 办公文档批量转 Markdown（Rust）',
    fields: [
      TaskFieldSpec(key: 'input_path', label: '输入文件/目录', type: TaskFieldType.file),
      TaskFieldSpec(
        key: 'binary_path',
        label: 'anydoc 二进制显式路径',
        type: TaskFieldType.file,
        advanced: true,
        optional: true,
      ),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        hint: '缺省：输入同目录 / md_out',
        optional: true,
      ),
    ],
  ),
  TaskTypeSpec(
    type: 'md2docx',
    label: '出库 MD→Word',
    glyph: '❖',
    description: 'md2docx 模板化转 Word（5 套场景模板）',
    fields: [
      TaskFieldSpec(key: 'input_path', label: '输入文件/目录', type: TaskFieldType.file),
      TaskFieldSpec(
        key: 'template',
        label: 'DOCX 模板',
        type: TaskFieldType.template,
        defaultValue: 'tech_doc',
      ),
      TaskFieldSpec(
        key: 'merge',
        label: '合并单文件（多 MD 合一 docx）',
        type: TaskFieldType.toggle,
        defaultValue: false,
      ),
      TaskFieldSpec(
        key: 'output_dir',
        label: '输出目录',
        type: TaskFieldType.directory,
        hint: '缺省：输入同目录 / docx_out',
        optional: true,
      ),
    ],
  ),
];

/// task_type → 环境体检项名（服务 env_manager.run_env_check 实名）。
/// 表单降级卡（UX P1：模块环境缺失时提交前禁用+环境缺失卡）；无对应体检项的
/// 类型不映射（禁伪造——如 wpd 无独立体检项）。
const taskTypeEnvKeys = <String, String>{
  'spider_single': 'Chromium 浏览器',
  'spider_site': 'Chromium 浏览器',
  'spider_pdf': 'Chromium 浏览器',
  'mineru': 'MinerU 模型目录',
  'anydoc': 'anydoc 二进制',
  'md2docx': 'DOCX 模板（5 套内置）',
};

/// URL 客户端预检（服务端 modules/_shared/url_guard 同语义收紧版）：
/// 仅 http/https；拒绝 localhost/.local/裸 IP 环回与私有段；拒绝无主机名。
/// 返回 null=通过；否则返回错误文案。
String? validateExternalUrl(String raw) {
  final value = raw.trim();
  if (value.isEmpty) return 'URL 不能为空';
  final Uri uri;
  try {
    uri = Uri.parse(value);
  } on FormatException {
    return 'URL 格式无法解析';
  }
  if (uri.scheme != 'http' && uri.scheme != 'https') {
    return '仅允许 http/https 协议';
  }
  final host = uri.host.toLowerCase();
  if (host.isEmpty) return 'URL 缺少主机名';
  if (host == 'localhost' || host.endsWith('.local')) return '禁止访问本机域名: $host';
  final pattern = RegExp(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$');
  final match = pattern.firstMatch(host);
  if (match != null) {
    final octets =
        match.groups([1, 2, 3, 4]).map((s) => int.parse(s!)).toList();
    // 环回 127/8、私有 10/8、172.16/12、192.168/16、链路本地 169.254/16、
    // 0.0.0.0/8 与保留段均拒绝（与 url_guard._check_ip 同族语义：
    // private+loopback+link_local+reserved+multicast+unspecified）
    final a = octets[0];
    final isReserved = a == 0 ||
        a == 10 ||
        a == 127 ||
        a >= 224 || // 组播 224/4 + 保留 240/4
        (a == 169 && octets[1] == 254) ||
        (a == 172 && octets[1] >= 16 && octets[1] <= 31) ||
        (a == 192 && octets[1] == 168);
    if (isReserved) return '禁止访问私有/保留地址: $host';
  }
  return null;
}

/// 拖拽扩展名 → 预填 task_type（§5.2 拖拽文件建任务映射）。
/// 返回 (task_type, 预填说明)；未命中扩展名返回 null（禁硬造）。
(String, String)? dropTargetForExtension(String ext) {
  switch (ext.toLowerCase()) {
    case '.pdf':
      return ('mineru', '解析 PDF');
    case '.docx':
    case '.doc':
    case '.xlsx':
    case '.pptx':
      return ('anydoc', '入库 Office→MD');
    case '.md':
      return ('md2docx', '出库 MD→Word');
  }
  return null;
}
