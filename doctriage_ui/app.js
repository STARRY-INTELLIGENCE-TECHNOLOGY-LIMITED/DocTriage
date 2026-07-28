const $ = (id) => document.getElementById(id);
const I18N = {
  "zh-CN": {
    app_title: "DocTriage 控制台",
    tab_analysis: "文档分析",
    tab_reading: "阅读台",
    tab_graph: "关系图谱",
    tab_rag: "RAG 索引",
    tab_agents: "Agent 编译",
    source_dir: "源目录",
    output_dir: "输出目录",
    current_output_root: "当前输出目录",
    source_mode_upload: "上传文档",
    upload_dialog_title: "上传文档",
    close: "关闭",
    add_upload_documents: "添加文档",
    pick_upload_files: "选择文件",
    pick_upload_folder: "选择文件夹",
    clear_upload_workspace: "清理上传",
    upload_empty: "尚未添加文档",
    folders_unit: "文件夹",
    pick_source_dir: "选择源目录",
    pick_output_dir: "选择输出目录",
    model: "模型",
    output_language: "输出语言",
    lang_auto: "自动",
    lang_zh: "中文",
    lang_en: "English",
    lang_ja: "日本語",
    lang_ko: "한국어",
    lang_de: "Deutsch",
    lang_fr: "Français",
    lang_es: "Español",
    start_analysis: "开始分析",
    stop_analysis: "停止分析",
    stop_relationships: "停止生成",
    reset_analysis: "重置分析",
    reset_relationships: "重置关系",
    reset_graph: "重置图谱",
    reading_output_root: "阅读目标输出目录",
    graph_output_root: "图谱分析目录",
    rag_output_root: "RAG 索引目录",
    anydocs_output_root: "DocTriage 输出目录",
    anydocs_url: "AnyDocsToAgents 地址",
    anydocs_bundle_path: "Bundle 路径",
    bundle_min_quality: "Bundle 最低质量",
    quality_stats_loading: "正在统计可导出文档...",
    quality_stats_unavailable: "暂无可用的质量分布。",
    quality_current_stats: "当前 {value}+：{count}/{total} 篇（{percent}%）",
    quality_distribution: "累计分布（阈值及以上）",
    quality_category_exclusions: "类别预排除：{count}/{total} 篇（{categories}）",
    pick_folder: "选择目录",
    reading_scope: "阅读范围",
    reading_filters: "搜索与过滤",
    scope_analysis: "分析结果",
    scope_source: "全部源文件",
    scope_source_unscored: "未分析",
    status: "状态",
    min_quality: "最低质量",
    category: "分类",
    keywords: "关键词",
    search: "搜索",
    max_sensitivity: "最高敏感",
    min_public: "最低公开适配",
    refresh: "刷新",
    select_all: "全选",
    invert: "反选",
    select_current_page: "全选当前页",
    clear_selection: "取消选择",
    bulk_reading: "批量在读",
    bulk_read: "批量已读",
    bulk_deferred: "批量稍后",
    bulk_skipped: "批量跳过",
    bulk_unread: "批量未读",
    open_next: "打开下一篇",
    export_filtered_csv: "导出当前筛选 CSV",
    export_filtered_jsonl: "导出当前筛选 JSONL",
    open: "打开",
    reveal: "定位",
    mark_reading: "在读",
    mark_read: "已读",
    mark_deferred: "稍后",
    mark_skipped: "跳过",
    mark_unread: "未读",
    disabled_open_title: "当前环境不支持调用系统默认阅读器",
    disabled_reveal_title: "当前环境不支持文件管理器定位",
    missing_source_title: "源文件不存在，无法打开或定位",
    table_select: "选择",
    table_quality: "质量",
    table_profile: "属性",
    table_type: "类型",
    table_sensitivity_compact: "敏感/公开",
    sensitivity_compact: "敏",
    public_compact: "公",
    table_name: "名称",
    table_modified: "修改时间",
    table_tags: "标签",
    table_actions: "操作",
    graph_search: "簇搜索",
    graph_min_size: "最小簇大小",
    vector_model: "向量模型",
    generate_relationships: "生成图谱",
    graph_log: "日志",
    export_bundle: "导出 Bundle",
    export_open_anydocs: "导出并打开 AnyDocsToAgents",
    refresh_graph: "刷新图谱",
    build_rag: "构建索引",
    stop_rag: "停止索引",
    rag_embedding_model: "Embedding 模型",
    rag_min_quality: "最低质量",
    rag_categories: "分类过滤",
    rag_limit: "文档上限",
    rag_chunk_max_chars: "切片长度",
    rag_chunk_overlap_chars: "重叠长度",
    analysis_advanced: "高级参数",
    rag_build_advanced: "索引参数",
    rag_advanced: "敏感词防火墙",
    vector_store_advanced: "向量存储",
    rag_redaction_enabled: "启用敏感词防火墙",
    rag_redact_drop_matched_documents: "命中后跳过文档",
    rag_redact_placeholder: "脱敏占位符",
    rag_redact_terms: "敏感词列表",
    rag_redact_mappings: "映射规则",
    rag_search_query: "检索测试",
    rag_top_k: "Top K",
    rag_search: "检索",
    concurrency: "并发",
    limit: "数量上限",
    max_mb: "最大 MB",
    quality_threshold: "质量阈值",
    timeout_seconds: "超时秒",
    summary: "摘要",
    plan_only: "仅评分，不复制文件",
    ocr_enabled: "开启OCR",
    manifest_analysis: "开启目录分析",
    mine_relationships: "挖掘关系",
    title_citations: "标题引用",
    embedding_relationships: "向量关系",
    status_unread: "未读",
    status_reading: "在读",
    status_read: "已读",
    status_reread_needed: "需重读",
    status_failed: "失败",
    status_skipped: "跳过",
    status_deferred: "稍后",
    status_all: "全部",
    no_summary: "无摘要",
    empty_graph: "暂无关系结果",
    graph_need_paths: "请先选择图谱分析目录",
    graph_no_match: "没有匹配的关系簇",
    graph_select_cluster: "选择一个关系簇查看文档详情",
    graph_no_docs: "这个关系簇没有可展示的文档",
    graph_no_edges: "当前文档没有可展示的关系边",
    related_documents: "关联文档",
    no_related_edges: "当前文档没有命中的关系边",
    no_explicit_signal: "无显式信号",
    uncategorized: "未分类",
    no_preview_path: "无预览路径",
    cluster: "簇",
    documents_unit: "篇",
    edges_unit: "条边",
    sensitive: "敏感",
    public_label: "公开",
    match_prefix: "匹配",
    all_prefix: "全部",
    first_page: "首页",
    previous_page: "上一页",
    next_page: "下一页",
    last_page: "末页",
    page_label: "第",
    page_suffix: "页",
    page_size_label: "数量",
    requested_open: "已请求打开",
    requested_reveal: "已请求定位",
    exported_rows: "已导出当前筛选",
    pick_failed: "选择失败",
    paths_apply_failed: "路径应用失败",
    paths_applied: "路径已应用",
    upload_creating: "正在创建上传工作区",
    upload_started: "正在上传 {count} 个文件",
    upload_complete: "上传完成：{count} 个文件，{size}",
    upload_failed: "上传失败",
    upload_cleared: "上传工作区已清理",
    upload_no_files: "请先选择文件",
    upload_incomplete: "上传尚未完成，请完成上传或清理上传工作区",
    source_or_upload_required: "请选择源目录或上传文档",
    output_required: "请选择输出目录",
    need_reading_output: "请先输入阅读目标输出目录",
    need_graph_output: "请先输入图谱分析目录",
    reading_output_apply_failed: "阅读目录应用失败",
    graph_output_apply_failed: "图谱目录应用失败",
    analysis_start_failed: "启动失败",
    analysis_started: "已启动分析",
    analysis_preempting_relationships: "正在停止生成关系并准备开始分析",
    embedding_model_required: "请先填写 Embedding 模型。",
    stop_requested: "已请求停止",
    stop_failed: "停止失败",
    relationship_stop_requested: "已请求停止生成关系",
    relationship_stop_failed: "停止生成关系失败",
    need_source_output: "请先应用源目录和输出目录",
    reset_confirm: "将清空输出目录中的日志、状态和关系结果：\n{output}\n\n如果该目录中存在已复制的分类文件，也会一并清理。该操作不可恢复，确认继续？",
    reset_relationships_confirm: "将清空该目录下的历史图谱和关系：\n{output}\\_relationships\n\n分析进度、阅读标记和 RAG 索引不会被删除。该操作不可恢复，确认继续？",
    reset_failed: "重置失败",
    output_reset: "输出目录已重置",
    relationship_reset_failed: "重置关系失败",
    relationships_reset: "图谱和关系已重置",
    reset_relationships_blocked_analysis: "分析运行中，请先停止分析再重置关系。",
    reset_relationships_blocked_relationships: "关系生成运行中，请先停止生成再重置关系。",
    status_load_failed: "状态加载失败",
    rows_load_failed: "加载失败",
    rows_loading: "正在加载阅读列表...",
    graph_load_failed: "图谱加载失败",
    graph_relations_exists: "存在 relations.jsonl",
    graph_clusters_exists: "存在 clusters.json",
    graph_decisions_exists: "存在 decisions.jsonl",
    graph_task_mine: "图谱生成",
    graph_task_export_graph: "知识图谱导出",
    graph_task_export_bundle: "Bundle 导出",
    graph_task_running: "{task}中",
    testing_llm: "正在检查模型链路",
    llm_check_failed: "模型链路检查失败",
    llm_check_ok: "模型链路可用",
    llm_check_reachable: "Endpoint 可达",
    llm_model_exists: "模型存在",
    llm_model_missing: "模型不存在",
    llm_model_unchecked: "未检查模型",
    graph_need_analysis_once: "先完成至少一次文档分析",
    graph_task_start_failed: "关系任务启动失败",
    graph_task_started: "已启动{task}",
    anydocs_export_failed: "Bundle 导出失败",
    anydocs_exported: "Bundle 已导出",
    anydocs_open_failed: "导出或打开 AnyDocsToAgents 失败",
    anydocs_opened: "Bundle 已导出并打开 AnyDocsToAgents",
    anydocs_github_opened: "Bundle 已导出；未检测到服务，已打开 GitHub 项目页",
    anydocs_github_open_failed: "Bundle 已导出；未检测到服务，请通过 GitHub 项目页获取 AnyDocsToAgents",
    anydocs_service_unavailable: "Bundle 已导出，但未检测到 {url} 的 AnyDocsToAgents 服务。请先安装并启动；已打开 GitHub 项目页。",
    anydocs_service_unavailable_github: "Bundle 已导出，但未检测到 {url} 的 AnyDocsToAgents 服务。请先安装并启动，可通过 GitHub 项目页获取。",
    anydocs_optional: "联动方式：Bundle 路径",
    rag_need_output: "请先输入 RAG 索引目录",
    rag_started: "已启动 RAG 索引",
    rag_start_failed: "RAG 索引启动失败",
    rag_stop_requested: "已请求停止 RAG 索引",
    rag_stop_failed: "停止 RAG 索引失败",
    rag_load_failed: "RAG 状态加载失败",
    rag_search_failed: "RAG 检索失败",
    rag_query_required: "请输入检索内容",
    rag_redaction_rules_required: "已启用敏感词防火墙，请先填写敏感词或映射规则。",
    rag_no_index: "暂无 RAG 索引",
    rag_no_results: "没有匹配结果",
    rag_documents_pill: "文档",
    rag_chunks_pill: "切片",
    rag_vectors_pill: "向量",
    rag_failed_pill: "失败文档",
    rag_phase_loading_decisions: "读取决策",
    rag_phase_extracting_text: "抽取正文",
    rag_phase_chunking: "写入切片",
    rag_phase_embedding: "生成向量",
    rag_phase_complete: "完成",
    rag_phase_error: "错误",
    rag_task_running: "RAG 索引中",
    vector_store_type: "向量库类型",
    vector_store_local: "本地 JSONL",
    vector_store_qdrant_local: "Qdrant 本地",
    vector_store_qdrant_remote: "Qdrant 服务（仅测试）",
    vector_store_chroma_remote: "Chroma 服务（仅测试）",
    vector_store_http_remote: "HTTP（仅测试）",
    vector_store_url: "存储路径或地址",
    vector_store_collection: "集合",
    test_vector_store: "测试向量库",
    testing_vector_store: "正在测试向量库",
    vector_store_test_failed: "向量库测试失败",
    vector_store_ok: "向量库可用",
    vector_store_unavailable: "向量库不可用",
    vector_store_reachable: "服务可达",
    vector_store_collection_exists: "集合存在",
    vector_store_collection_missing: "集合不存在",
    vector_store_vectors: "向量记录",
    rag_result_count: "结果",
    rag_mode_vector: "向量检索",
    rag_mode_lexical: "词法检索",
    graph_cluster_load_failed: "关系簇加载失败",
    graph_task_running_refresh: "{task}中，请稍后刷新",
    graph_need_analysis_before_graph: "先完成一次文档分析，再生成关系图谱",
    graph_no_relationships_generate: "还没有图谱结果，可点击“生成图谱”",
    graph_task_running_detail: "后台任务运行中。局部图与证据将在任务完成后显示。",
    graph_generate_then_detail: "尚未生成关系图谱。",
    graph_phase_loading_decisions: "读取决策",
    graph_phase_records_loaded: "决策已读取",
    graph_phase_preparing_embeddings: "准备 Embedding",
    graph_phase_scoring_relationships: "计算关系",
    graph_phase_writing_relations: "写入关系",
    graph_phase_clustering: "生成聚类",
    graph_phase_complete: "完成",
    graph_phase_error: "错误",
    graph_records_pill: "文档",
    graph_candidates_pill: "候选关系",
    graph_embedded_pill: "向量",
    mark_failed: "标记失败",
    marked_status: "已标记：{status}",
    select_documents_first: "请先选择文档",
    bulk_mark_failed: "批量标记失败",
    bulk_marked: "已批量标记 {count} 篇",
    current_list_empty: "当前列表为空",
    sort_public_desc: "公开↓",
    sort_public_asc: "公开↑",
    plan_only_pill: "仅评分：只记录评分与阅读标记，不复制文件",
    running_pill: "运行中",
    not_running_pill: "未运行",
    progress_pill: "进度",
    elapsed_pill: "耗时",
    embedding_progress_pill: "Embedding 向量",
    embedding_phase_loading_cache: "读取缓存",
    embedding_phase_embedding: "生成中",
    embedding_phase_complete: "完成",
    embedding_phase_ready: "准备",
    embedding_speed_waiting_pill: "速度等待连续生成",
    embedding_eta_waiting_pill: "ETA 等待连续生成",
    eta_finish_pill: "预计完成",
    completed_pill: "完成",
    concurrency_pill: "并发",
    eta_waiting_pill: "ETA 等待连续规划",
    speed_pill: "速度",
    speed_waiting_pill: "速度等待连续规划",
    unresolved_failures_pill: "未解决失败",
    retry_recovered_pill: "重试恢复",
    stale_lock_pid_pill: "陈旧锁 PID",
    phase_not_started: "未启动",
    phase_relationship_mining: "关系挖掘中",
    phase_resume_preparing: "续传准备中",
    phase_resume_skipping: "续传跳过中",
    phase_scoring: "文档评分中",
    phase_scanning: "扫描准备中",
    phase_completed_with_failures: "分析完成，仍有失败",
    phase_completed_relationships: "分析完成，关系已生成",
    phase_completed_no_relationships: "分析完成，关系未生成",
    phase_completed: "分析完成",
    phase_stopped_resume: "已停止，可续传",
    explain_summary: "摘要",
    explain_reason: "评分理由",
    explain_dimensions: "维度",
    explain_failure: "失败",
    explain_failure_stage: "阶段",
    explain_failure_reason: "原因",
    explain_failure_attempts: "尝试",
    explain_failure_error: "错误",
    dim_knowledge_density: "知识密度",
    dim_implementation_specificity: "实现细节",
    dim_logical_structure: "逻辑结构",
    dim_evidence_richness: "证据",
    dim_actionability: "可执行",
    dim_strategic_value: "战略",
    dim_freshness: "新鲜",
    dim_uniqueness: "独特",
    folder_picker_unavailable: "当前环境不支持图形目录选择，请手工输入路径",
    operation_failed: "操作失败",
    tip_current_output_root: "阅读台、关系图谱、RAG 索引与 Agent 编译共用此目录；不影响分析页路径。",
    tip_bundle_min_quality: "导出质量分不低于阈值的文档。默认值为 0；不继承其他页面的阈值。",
    tip_upload_source: "文件上传至服务器工作区，分析任务读取服务器副本。",
    tip_source_dir: "递归扫描此目录内受支持的文档。输出目录不得位于其中。",
    tip_output_dir: "保存进度、日志、评分及复制结果；支持续跑，且仅允许单进程写入。",
    tip_llm_endpoint: "文档评分使用的文本模型接口。Ollama 默认路径：/api/generate。",
    tip_model: "文档分类、评分与摘要模型。向量关系使用单独的向量模型。",
    tip_llm_api_key: "OpenAI 兼容接口的 Bearer Token。本地 Ollama 可留空；不写入浏览器存储。",
    tip_embedding_api_key: "向量接口的 Bearer Token。留空时使用 LLM API Key；不写入浏览器存储。",
    tip_output_language: "摘要与评分理由的语言。自动模式按文档正文识别。",
    tip_concurrency: "并发模型请求数。本地模型或大批量任务建议从 1 开始。",
    tip_limit: "仅处理前 N 个候选文件；留空为全量。",
    tip_max_mb: "跳过大于此值的文件。",
    tip_quality_threshold: "达到阈值的文档标记为高价值候选。仅评分模式不生成分类目录。",
    tip_timeout_seconds: "单次模型请求的最长等待时间。",
    tip_summary: "将短摘要写入 decisions.jsonl，供关系分析、公开写作筛选和人工复核使用。",
    tip_plan_only: "记录评分、分类、进度与决策，不复制源文件。",
    tip_ocr_enabled: "解析图片及扫描版 PDF；增加处理时长。",
    tip_manifest_analysis: "文件评分前执行目录级系列与集合分析。",
    tip_mine_relationships: "评分完成后生成关系和聚类文件：_relationships/relations.jsonl、clusters.json。",
    tip_title_citations: "使用标题和路径提取引用关系，不调用向量模型。",
    tip_embedding_relationships: "基于摘要、标题和分类生成向量关系。填写模型后启用；留空时使用规则与标题引用。",
    tip_rag_output_root: "已分析的输出目录；索引写入 _rag。",
    tip_rag_embedding_model: "留空时仅构建文档和切片；填写后生成 _rag/vectors.jsonl 并启用语义检索。",
    tip_rag_redaction_enabled: "仅处理 RAG 索引文本，不修改分析结果。脱敏在写入 _rag 或向量库前执行。",
    tip_rag_redact_drop_matched_documents: "正文命中敏感词或映射规则时，文档不进入切片、向量及后续向量库。",
    tip_rag_redact_placeholder: "敏感词替换文本，默认为 [REDACTED]。",
    tip_rag_redact_terms: "每行一个词或使用英文逗号分隔；命中内容替换为占位符。",
    tip_rag_redact_mappings: "每行一条 原文=>映射值；regex: 启用正则，case: 区分大小写。",
    tip_vector_store_type: "Qdrant 本地参与索引写入和检索；本地 JSONL 为默认存储；其余类型仅测试连接。",
    tip_vector_store_url: "Qdrant 本地可留空，默认写入 _rag/qdrant；服务类型填写 URL。",
    tip_vector_store_collection: "Qdrant 本地默认使用 doctriage_rag；服务类型填写时检查集合是否存在。",
    tip_rag_search_query: "优先向量检索；无向量时使用词法检索。",
    ph_source_dir: "请选择源文档目录",
    ph_output_dir: "请选择输出目录",
    ph_reading_output_root: "选择或输入已分析输出目录",
    ph_graph_output_root: "选择或输入已分析输出目录",
    ph_rag_output_root: "选择或输入已分析输出目录",
    ph_vector_store_url: "本地类型可留空",
    ph_vector_store_collection: "doctriage_rag",
    ph_text_search: "名称/路径/备注",
    ph_graph_search: "路径/分类/标签",
    ph_limit: "空为全量",
    ph_api_key_optional: "本地 Ollama 可留空",
    ph_embedding_api_key: "留空沿用 LLM API Key",
    ph_embedding_model: "留空则不生成向量关系",
    ph_rag_embedding_model: "留空则仅构建文本索引",
    ph_rag_categories: "可多选",
    ph_rag_redact_terms: "一行一个，或逗号分隔",
    ph_rag_redact_mappings: "原文=>映射值\nregex:\\b1[3-9]\\d{9}\\b=>[PHONE]",
    ph_rag_query: "输入问题、主题或关键词"
  },
  en: {
    app_title: "DocTriage Console",
    tab_analysis: "Document Analysis",
    tab_reading: "Reading",
    tab_graph: "Graph",
    tab_rag: "RAG Index",
    tab_agents: "Agent compile",
    source_dir: "Source directory",
    output_dir: "Output directory",
    current_output_root: "Current output directory",
    source_mode_upload: "Upload documents",
    upload_dialog_title: "Upload documents",
    close: "Close",
    add_upload_documents: "Add documents",
    pick_upload_files: "Choose files",
    pick_upload_folder: "Choose folder",
    clear_upload_workspace: "Clear upload",
    upload_empty: "No documents added",
    folders_unit: "Folders",
    pick_source_dir: "Pick source",
    pick_output_dir: "Pick output",
    model: "Model",
    output_language: "Output language",
    lang_auto: "Auto",
    lang_zh: "Chinese",
    lang_en: "English",
    lang_ja: "Japanese",
    lang_ko: "Korean",
    lang_de: "German",
    lang_fr: "French",
    lang_es: "Spanish",
    start_analysis: "Start analysis",
    stop_analysis: "Stop analysis",
    stop_relationships: "Stop generation",
    reset_analysis: "Reset analysis",
    reset_relationships: "Reset relationships",
    reset_graph: "Reset graph",
    reading_output_root: "Reading output directory",
    graph_output_root: "Graph analysis directory",
    rag_output_root: "RAG index directory",
    anydocs_output_root: "DocTriage output directory",
    anydocs_url: "AnyDocsToAgents URL",
    anydocs_bundle_path: "Bundle path",
    bundle_min_quality: "Bundle min quality",
    quality_stats_loading: "Counting exportable documents...",
    quality_stats_unavailable: "Quality distribution is unavailable.",
    quality_current_stats: "Current {value}+: {count}/{total} docs ({percent}%)",
    quality_distribution: "Cumulative distribution (threshold and above)",
    quality_category_exclusions: "Category pre-filter: {count}/{total} docs ({categories})",
    pick_folder: "Pick folder",
    reading_scope: "Reading scope",
    reading_filters: "Search and filters",
    scope_analysis: "Analysis results",
    scope_source: "All source files",
    scope_source_unscored: "Unscored",
    status: "Status",
    min_quality: "Min quality",
    category: "Category",
    keywords: "Keywords",
    search: "Search",
    max_sensitivity: "Max sensitivity",
    min_public: "Min public suitability",
    refresh: "Refresh",
    select_all: "Select all",
    invert: "Invert",
    select_current_page: "Select current page",
    clear_selection: "Clear selection",
    bulk_reading: "Bulk reading",
    bulk_read: "Bulk read",
    bulk_deferred: "Bulk defer",
    bulk_skipped: "Bulk skip",
    bulk_unread: "Bulk unread",
    open_next: "Open next",
    export_filtered_csv: "Export filtered CSV",
    export_filtered_jsonl: "Export filtered JSONL",
    open: "Open",
    reveal: "Reveal",
    mark_reading: "Reading",
    mark_read: "Read",
    mark_deferred: "Defer",
    mark_skipped: "Skip",
    mark_unread: "Unread",
    disabled_open_title: "System default file opening is unavailable in this environment",
    disabled_reveal_title: "File-manager reveal is unavailable in this environment",
    missing_source_title: "Source file does not exist",
    table_select: "Select",
    table_quality: "Quality",
    table_profile: "Profile",
    table_type: "Type",
    table_sensitivity_compact: "Risk/Public",
    sensitivity_compact: "Risk",
    public_compact: "Public",
    table_name: "Name",
    table_modified: "Modified",
    table_tags: "Tags",
    table_actions: "Actions",
    graph_search: "Cluster search",
    graph_min_size: "Min cluster size",
    vector_model: "Vector model",
    generate_relationships: "Generate graph",
    graph_log: "Log",
    export_bundle: "Export bundle",
    export_open_anydocs: "Export and open AnyDocsToAgents",
    refresh_graph: "Refresh graph",
    build_rag: "Build index",
    stop_rag: "Stop index",
    rag_embedding_model: "Embedding model",
    rag_min_quality: "Min quality",
    rag_categories: "Category filter",
    rag_limit: "Document limit",
    rag_chunk_max_chars: "Chunk length",
    rag_chunk_overlap_chars: "Overlap length",
    analysis_advanced: "Advanced parameters",
    rag_build_advanced: "Index parameters",
    rag_advanced: "Sensitive firewall",
    vector_store_advanced: "Vector storage",
    rag_redaction_enabled: "Enable sensitive firewall",
    rag_redact_drop_matched_documents: "Skip matched documents",
    rag_redact_placeholder: "Redaction placeholder",
    rag_redact_terms: "Sensitive terms",
    rag_redact_mappings: "Mapping rules",
    rag_search_query: "Search test",
    rag_top_k: "Top K",
    rag_search: "Search",
    concurrency: "Concurrency",
    limit: "Limit",
    max_mb: "Max MB",
    quality_threshold: "Quality threshold",
    timeout_seconds: "Timeout seconds",
    summary: "Summary",
    plan_only: "Score only, do not copy files",
    ocr_enabled: "Enable OCR",
    manifest_analysis: "Enable directory analysis",
    mine_relationships: "Mine relationships",
    title_citations: "Title citations",
    embedding_relationships: "Vector relationships",
    status_unread: "Unread",
    status_reading: "Reading",
    status_read: "Read",
    status_reread_needed: "Reread needed",
    status_failed: "Failed",
    status_skipped: "Skipped",
    status_deferred: "Deferred",
    status_all: "All",
    no_summary: "No summary",
    empty_graph: "No relationship results",
    graph_need_paths: "Select a graph analysis directory first",
    graph_no_match: "No matching relationship clusters",
    graph_select_cluster: "Select a relationship cluster to inspect documents",
    graph_no_docs: "This cluster has no displayable documents",
    graph_no_edges: "The selected document has no displayable relationship edges",
    related_documents: "Related documents",
    no_related_edges: "The selected document has no matching relationship edges",
    no_explicit_signal: "No explicit signal",
    uncategorized: "Uncategorized",
    no_preview_path: "No preview path",
    cluster: "Cluster",
    documents_unit: "docs",
    edges_unit: "edges",
    sensitive: "Sensitive",
    public_label: "Public",
    match_prefix: "Matched",
    all_prefix: "All",
    first_page: "First",
    previous_page: "Previous",
    next_page: "Next",
    last_page: "Last",
    page_label: "Page",
    page_suffix: "",
    page_size_label: "Page size",
    requested_open: "Open requested",
    requested_reveal: "Reveal requested",
    exported_rows: "Filtered rows exported",
    pick_failed: "Selection failed",
    paths_apply_failed: "Failed to apply paths",
    paths_applied: "Paths applied",
    upload_creating: "Creating upload workspace",
    upload_started: "Uploading {count} files",
    upload_complete: "Upload complete: {count} files, {size}",
    upload_failed: "Upload failed",
    upload_cleared: "Upload workspace cleared",
    upload_no_files: "Choose files first",
    upload_incomplete: "Upload is incomplete. Finish it or clear the upload workspace",
    source_or_upload_required: "Choose a source directory or upload documents",
    output_required: "Choose an output directory",
    need_reading_output: "Enter a reading output directory first",
    need_graph_output: "Enter a graph analysis directory first",
    reading_output_apply_failed: "Failed to apply reading directory",
    graph_output_apply_failed: "Failed to apply graph directory",
    analysis_start_failed: "Failed to start analysis",
    analysis_started: "Analysis started",
    analysis_preempting_relationships: "Stopping relationship generation and preparing analysis",
    embedding_model_required: "Enter an embedding model first.",
    stop_requested: "Stop requested",
    stop_failed: "Failed to stop",
    relationship_stop_requested: "Relationship stop requested",
    relationship_stop_failed: "Failed to stop relationship generation",
    need_source_output: "Apply source and output directories first",
    reset_confirm: "This will clear logs, status, and relationship results in the output directory:\n{output}\n\nCopied routed files in that directory will also be removed. This cannot be undone. Continue?",
    reset_relationships_confirm: "This will clear historical graph and relationship outputs in:\n{output}\\_relationships\n\nAnalysis progress, reading marks, and RAG indexes will not be deleted. This cannot be undone. Continue?",
    reset_failed: "Reset failed",
    output_reset: "Output directory reset",
    relationship_reset_failed: "Failed to reset relationship outputs",
    relationships_reset: "Graph and relationship outputs reset",
    reset_relationships_blocked_analysis: "Analysis is running. Stop analysis before resetting relationships.",
    reset_relationships_blocked_relationships: "Relationship generation is running. Stop generation before resetting relationships.",
    status_load_failed: "Failed to load status",
    rows_load_failed: "Failed to load rows",
    rows_loading: "Loading reading list...",
    graph_load_failed: "Failed to load graph",
    graph_relations_exists: "relations.jsonl exists",
    graph_clusters_exists: "clusters.json exists",
    graph_decisions_exists: "decisions.jsonl exists",
    graph_task_mine: "Graph generation",
    graph_task_export_graph: "Graph export",
    graph_task_export_bundle: "Bundle export",
    graph_task_running: "{task} running",
    testing_llm: "Checking model endpoint",
    llm_check_failed: "Model endpoint check failed",
    llm_check_ok: "Model endpoint is ready",
    llm_check_reachable: "Endpoint reachable",
    llm_model_exists: "Model exists",
    llm_model_missing: "Model missing",
    llm_model_unchecked: "Model unchecked",
    graph_need_analysis_once: "Complete at least one document analysis first",
    graph_task_start_failed: "Failed to start relationship task",
    graph_task_started: "Started {task}",
    anydocs_export_failed: "Failed to export bundle",
    anydocs_exported: "Bundle exported",
    anydocs_open_failed: "Failed to export or open AnyDocsToAgents",
    anydocs_opened: "Bundle exported and AnyDocsToAgents opened",
    anydocs_github_opened: "Bundle exported; service not detected, so the GitHub project page was opened",
    anydocs_github_open_failed: "Bundle exported; service not detected, so get AnyDocsToAgents from its GitHub project page",
    anydocs_service_unavailable: "The bundle was exported, but no AnyDocsToAgents service was detected at {url}. Install and start it first; the GitHub project page was opened.",
    anydocs_service_unavailable_github: "The bundle was exported, but no AnyDocsToAgents service was detected at {url}. Install and start it first; the project is available on GitHub.",
    anydocs_optional: "Integration: Bundle path",
    rag_need_output: "Enter a RAG index directory first",
    rag_started: "RAG indexing started",
    rag_start_failed: "Failed to start RAG indexing",
    rag_stop_requested: "RAG stop requested",
    rag_stop_failed: "Failed to stop RAG indexing",
    rag_load_failed: "Failed to load RAG status",
    rag_search_failed: "RAG search failed",
    rag_query_required: "Enter a search query",
    rag_redaction_rules_required: "Sensitive firewall is enabled. Enter sensitive terms or mapping rules first.",
    rag_no_index: "No RAG index yet",
    rag_no_results: "No matching results",
    rag_documents_pill: "Documents",
    rag_chunks_pill: "Chunks",
    rag_vectors_pill: "Vectors",
    rag_failed_pill: "Failed docs",
    rag_phase_loading_decisions: "Loading decisions",
    rag_phase_extracting_text: "Extracting text",
    rag_phase_chunking: "Writing chunks",
    rag_phase_embedding: "Embedding",
    rag_phase_complete: "Complete",
    rag_phase_error: "Error",
    rag_task_running: "RAG indexing",
    vector_store_type: "Vector store",
    vector_store_local: "Local JSONL",
    vector_store_qdrant_local: "Qdrant Local",
    vector_store_qdrant_remote: "Qdrant service (test only)",
    vector_store_chroma_remote: "Chroma service (test only)",
    vector_store_http_remote: "HTTP (test only)",
    vector_store_url: "Storage path or URL",
    vector_store_collection: "Collection",
    test_vector_store: "Test vector store",
    testing_vector_store: "Testing vector store",
    vector_store_test_failed: "Vector store test failed",
    vector_store_ok: "Vector store ready",
    vector_store_unavailable: "Vector store unavailable",
    vector_store_reachable: "Service reachable",
    vector_store_collection_exists: "Collection exists",
    vector_store_collection_missing: "Collection missing",
    vector_store_vectors: "Vector records",
    rag_result_count: "Results",
    rag_mode_vector: "Vector search",
    rag_mode_lexical: "Lexical search",
    graph_cluster_load_failed: "Failed to load relationship cluster",
    graph_task_running_refresh: "{task} is running. Refresh later.",
    graph_need_analysis_before_graph: "Complete one document analysis before generating the graph",
    graph_no_relationships_generate: "No graph results yet. Click Generate graph.",
    graph_task_running_detail: "Background task running. The local graph and evidence appear after completion.",
    graph_generate_then_detail: "No relationship graph has been generated.",
    graph_phase_loading_decisions: "Loading decisions",
    graph_phase_records_loaded: "Decisions loaded",
    graph_phase_preparing_embeddings: "Preparing embeddings",
    graph_phase_scoring_relationships: "Scoring relationships",
    graph_phase_writing_relations: "Writing relations",
    graph_phase_clustering: "Building clusters",
    graph_phase_complete: "Complete",
    graph_phase_error: "Error",
    graph_records_pill: "Documents",
    graph_candidates_pill: "Candidate relations",
    graph_embedded_pill: "Vectors",
    mark_failed: "Failed to mark document",
    marked_status: "Marked: {status}",
    select_documents_first: "Select documents first",
    bulk_mark_failed: "Failed to mark selected documents",
    bulk_marked: "Marked {count} docs",
    current_list_empty: "The current list is empty",
    sort_public_desc: "Public↓",
    sort_public_asc: "Public↑",
    plan_only_pill: "Plan only: score and mark reading status without copying files",
    running_pill: "Running",
    not_running_pill: "Not running",
    progress_pill: "Progress",
    elapsed_pill: "Elapsed",
    embedding_progress_pill: "Embedding vectors",
    embedding_phase_loading_cache: "Loading cache",
    embedding_phase_embedding: "Generating",
    embedding_phase_complete: "Complete",
    embedding_phase_ready: "Ready",
    embedding_speed_waiting_pill: "Speed waiting for steady generation",
    embedding_eta_waiting_pill: "ETA waiting for steady generation",
    eta_finish_pill: "Finish",
    completed_pill: "Completed",
    concurrency_pill: "Concurrency",
    eta_waiting_pill: "ETA waiting for steady planning",
    speed_pill: "Speed",
    speed_waiting_pill: "Speed waiting for steady planning",
    unresolved_failures_pill: "Unresolved failures",
    retry_recovered_pill: "Retry recovered",
    stale_lock_pid_pill: "Stale lock PID",
    phase_not_started: "Not started",
    phase_relationship_mining: "Mining relationships",
    phase_resume_preparing: "Preparing resume",
    phase_resume_skipping: "Resume skipping",
    phase_scoring: "Scoring documents",
    phase_scanning: "Preparing scan",
    phase_completed_with_failures: "Analysis complete, failures remain",
    phase_completed_relationships: "Analysis complete, relationships generated",
    phase_completed_no_relationships: "Analysis complete, relationships not generated",
    phase_completed: "Analysis complete",
    phase_stopped_resume: "Stopped, resumable",
    explain_summary: "Summary",
    explain_reason: "Scoring reason",
    explain_dimensions: "Dimensions",
    explain_failure: "Failure",
    explain_failure_stage: "Stage",
    explain_failure_reason: "Reason",
    explain_failure_attempts: "Attempts",
    explain_failure_error: "Error",
    dim_knowledge_density: "Knowledge",
    dim_implementation_specificity: "Implementation",
    dim_logical_structure: "Structure",
    dim_evidence_richness: "Evidence",
    dim_actionability: "Actionability",
    dim_strategic_value: "Strategic",
    dim_freshness: "Freshness",
    dim_uniqueness: "Uniqueness",
    folder_picker_unavailable: "Folder picker is unavailable here; type the path manually",
    operation_failed: "Operation failed",
    tip_current_output_root: "Shared output directory for Reading, Graph, RAG, and Agent Compilation; Analysis paths are unchanged.",
    tip_bundle_min_quality: "Exports documents at or above this score. Default: 0. Thresholds from other pages are not inherited.",
    tip_upload_source: "Files are uploaded to the server workspace and analyzed from the server copy.",
    tip_source_dir: "Recursively scans supported documents in this directory. The output directory must be outside it.",
    tip_output_dir: "Stores progress, logs, scores, and copied files; supports resume and single-process writes.",
    tip_llm_endpoint: "Text-model endpoint for document scoring. Default Ollama path: /api/generate.",
    tip_model: "Model for document classification, scoring, and summaries. Vector relationships use a separate model.",
    tip_llm_api_key: "Bearer token for OpenAI-compatible endpoints. Optional for local Ollama; not stored in the browser.",
    tip_embedding_api_key: "Bearer token for the embedding endpoint. Empty uses the LLM API key; not stored in the browser.",
    tip_output_language: "Language for summaries and scoring reasons. Auto detects the document language.",
    tip_concurrency: "Concurrent model requests. Start at 1 for local models or large batches.",
    tip_limit: "Processes the first N candidate files; empty processes all files.",
    tip_max_mb: "Skips files larger than this value.",
    tip_quality_threshold: "Marks documents at or above the threshold as high-value candidates. Plan-only mode does not create category folders.",
    tip_timeout_seconds: "Maximum duration of one model request.",
    tip_summary: "Writes short summaries to decisions.jsonl for relationship analysis, publication review, and manual triage.",
    tip_plan_only: "Records scores, categories, progress, and decisions without copying source files.",
    tip_ocr_enabled: "Parses images and scanned PDFs; increases processing time.",
    tip_manifest_analysis: "Runs directory-level series and collection analysis before file scoring.",
    tip_mine_relationships: "Creates _relationships/relations.jsonl and clusters.json after scoring.",
    tip_title_citations: "Extracts citation relationships from titles and paths without an embedding model.",
    tip_embedding_relationships: "Builds vector relationships from summaries, titles, and categories. A model enables it; empty uses rules and title citations.",
    tip_rag_output_root: "Analyzed output directory; the index is written to _rag.",
    tip_rag_embedding_model: "Empty builds documents and chunks only; a model also creates _rag/vectors.jsonl and enables semantic search.",
    tip_rag_redaction_enabled: "Processes RAG index text only. Redaction runs before writing to _rag or vector storage.",
    tip_rag_redact_drop_matched_documents: "Documents matching a sensitive term or mapping rule are excluded from chunks, vectors, and later vector storage.",
    tip_rag_redact_placeholder: "Replacement text for sensitive terms. Default: [REDACTED].",
    tip_rag_redact_terms: "One term per line or comma-separated; matches are replaced by the placeholder.",
    tip_rag_redact_mappings: "One original=>mapped rule per line; regex: enables regular expressions and case: enables case sensitivity.",
    tip_vector_store_type: "Qdrant Local participates in index writes and search. Local JSONL is the default store; other types only test connectivity.",
    tip_vector_store_url: "Qdrant Local defaults to _rag/qdrant when empty. Enter a URL for service types.",
    tip_vector_store_collection: "Qdrant Local defaults to doctriage_rag. Service types check the collection when supplied.",
    tip_rag_search_query: "Uses vector search first and lexical search when vectors are unavailable.",
    ph_source_dir: "Select source document directory",
    ph_output_dir: "Select output directory",
    ph_reading_output_root: "Select or enter an analyzed output directory",
    ph_graph_output_root: "Select or enter an analyzed output directory",
    ph_rag_output_root: "Select or enter an analyzed output directory",
    ph_vector_store_url: "empty for local storage",
    ph_vector_store_collection: "doctriage_rag",
    ph_text_search: "Name/path/note",
    ph_graph_search: "Path/category/tag",
    ph_limit: "empty means all",
    ph_api_key_optional: "empty for local Ollama",
    ph_embedding_api_key: "empty reuses LLM API key",
    ph_embedding_model: "empty disables embedding relationships",
    ph_rag_embedding_model: "empty builds text index only",
    ph_rag_categories: "multi-select",
    ph_rag_redact_terms: "one per line, or comma-separated",
    ph_rag_redact_mappings: "original=>mapped\nregex:\\b1[3-9]\\d{9}\\b=>[PHONE]",
    ph_rag_query: "Enter a question, topic, or keyword"
  }
};
let uiLanguage = localStorage.getItem("doctriage_ui_language") || "zh-CN";
let allRows = [];
let filteredRows = [];
let currentRows = [];
let readingRowsLoading = false;
let readingRowsLoadedKey = "";
let readingRowsLoadingKey = "";
let readingRowsLoadToken = 0;
let capabilities = {};
let currentPage = 1;
let pageSize = Number(localStorage.getItem("doctriage_page_size") || 100);
let readingScope = localStorage.getItem("doctriage_reading_scope") || "analysis";
let sortKey = localStorage.getItem(sortStorageKey(readingScope)) || defaultSortForScope(readingScope);
let graphMeta = {};
let graphClusters = [];
let filteredGraphClusters = [];
let graphSelectedClusterId = null;
let graphClusterData = null;
let graphSelectedDocPath = "";
let graphClearMessageKey = "empty_graph";
let ragMeta = {};
let ragSearchPayload = null;
let tooltipTarget = null;
let readingSourceDir = "";
let lastSyncedRunOutputRoot = "";
let lastAppliedRunPathKey = "";
let graphSourceDir = "";
let lastSyncedGraphOutputRoot = "";
let ragSourceDir = "";
let lastSyncedRagOutputRoot = "";
let anydocsSourceDir = "";
let lastSyncedAnydocsOutputRoot = "";
let anydocsStandaloneBundleMinQuality = "0";
let anydocsBundleQualityHistogram = [];
let anydocsBundleQualityTotal = 0;
let anydocsBundleSourceTotal = 0;
let anydocsBundleExcludedCategoryCount = 0;
let anydocsBundleExcludedCategories = [];
let anydocsQualityStatsKey = "";
let anydocsUnavailableServiceUrl = "";
let anydocsGithubOpened = false;
let lastAnalysisPayload = null;
let relationshipLaunchPending = null;
let relationshipStopPending = null;
let lastEmbeddingProgress = null;
let lastEmbeddingTask = null;
let analysisActionBusy = false;
let relationshipActionBusy = false;
let graphActionBusy = false;
let ragActionBusy = false;
let relationshipLaunchToken = 0;
let configuredEmbeddingEndpoint = "";
let currentUploadWorkspace = null;
let uploadBusy = false;
const DEFAULT_EMBEDDING_ENDPOINT = "http://localhost:11434/api/embeddings";
const RUN_FORM_STORAGE_KEY = "doctriage_run_form";
const RUN_FORM_STORAGE_VERSION = 4;
const READING_TARGET_STORAGE_KEY = "doctriage_reading_target";
const GRAPH_TARGET_STORAGE_KEY = "doctriage_graph_target";
const RAG_TARGET_STORAGE_KEY = "doctriage_rag_target";
const ANYDOCS_TARGET_STORAGE_KEY = "doctriage_anydocs_target";
const DEFAULT_ANYDOCS_URL = "http://127.0.0.1:18766/";
const RUN_FORM_VALUE_FIELDS = [
  "run_source_dir",
  "run_output_root",
  "run_llm_endpoint",
  "run_llm_model",
  "run_output_language",
  "run_concurrency",
  "run_limit",
  "run_max_file_size_mb",
  "run_quality_threshold",
  "run_timeout_seconds"
];
const GRAPH_FORM_VALUE_FIELDS = [
  "run_embedding_model"
];
const GRAPH_FORM_ALLOW_EMPTY_FIELDS = new Set([
  "run_embedding_model"
]);
const RUN_FORM_SECRET_FIELDS = [
  "run_llm_api_key",
  "run_embedding_api_key"
];
const RUN_FORM_CHECKBOX_FIELDS = [
  "run_plan_only",
  "run_ocr_enabled"
];
const RUN_FORM_ALLOW_EMPTY_FIELDS = new Set([
  "run_limit"
]);
const EXPLANATION_DIMENSIONS = [
  ["knowledge_density", "dim_knowledge_density"],
  ["implementation_specificity", "dim_implementation_specificity"],
  ["logical_structure", "dim_logical_structure"],
  ["evidence_richness", "dim_evidence_richness"],
  ["actionability", "dim_actionability"],
  ["strategic_value", "dim_strategic_value"],
  ["freshness", "dim_freshness"],
  ["uniqueness", "dim_uniqueness"]
];

function readingParams() {
  const pairs = new URLSearchParams();
  pairs.set("sort", sortKey);
  pairs.set("scope", readingScope);
  const paths = readingPathPayload();
  if (paths.source_dir) pairs.set("source_dir", paths.source_dir);
  if (paths.output_root) pairs.set("output_root", paths.output_root);
  return pairs.toString();
}

function sortStorageKey(scope) {
  return scope === "source" ? "doctriage_reading_sort_source" : "doctriage_reading_sort_analysis";
}

function defaultSortForScope(scope) {
  return scope === "source" ? "source_path_asc" : "quality_desc";
}

function tr(key) {
  return (I18N[uiLanguage] && I18N[uiLanguage][key]) || I18N["zh-CN"][key] || key;
}

function trf(key, values = {}) {
  let text = tr(key);
  for (const [name, value] of Object.entries(values)) {
    text = text.split(`{${name}}`).join(String(value ?? ""));
  }
  return text;
}

function readStoredRunFormState() {
  try {
    const raw = localStorage.getItem(RUN_FORM_STORAGE_KEY);
    if (!raw) return {};
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function currentRunFormState() {
  const state = {_version: RUN_FORM_STORAGE_VERSION};
  for (const id of RUN_FORM_VALUE_FIELDS) {
    const element = $(id);
    if (element) state[id] = element.value;
  }
  for (const id of GRAPH_FORM_VALUE_FIELDS) {
    const element = $(id);
    if (element) state[id] = element.value;
  }
  for (const id of RUN_FORM_CHECKBOX_FIELDS) {
    const element = $(id);
    if (element) state[id] = !!element.checked;
  }
  return state;
}

function saveRunFormState() {
  try {
    localStorage.setItem(RUN_FORM_STORAGE_KEY, JSON.stringify(currentRunFormState()));
  } catch (error) {
    // Browser storage can be disabled or full; the form still works without persistence.
  }
}

function readStoredReadingTargetState() {
  try {
    const raw = localStorage.getItem(READING_TARGET_STORAGE_KEY);
    if (!raw) return {};
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function saveReadingTargetState() {
  try {
    localStorage.setItem(READING_TARGET_STORAGE_KEY, JSON.stringify(readingPathPayload()));
  } catch (error) {
    // Browser storage can be disabled or full; reading still works without persistence.
  }
}

function readStoredGraphTargetState() {
  try {
    const raw = localStorage.getItem(GRAPH_TARGET_STORAGE_KEY);
    if (!raw) return {};
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function saveGraphTargetState() {
  try {
    localStorage.setItem(GRAPH_TARGET_STORAGE_KEY, JSON.stringify(currentGraphTargetState()));
  } catch (error) {
    // Browser storage can be disabled or full; graph still works without persistence.
  }
}

function readStoredRagTargetState() {
  try {
    const raw = localStorage.getItem(RAG_TARGET_STORAGE_KEY);
    if (!raw) return {};
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function saveRagTargetState() {
  try {
    localStorage.setItem(RAG_TARGET_STORAGE_KEY, JSON.stringify(currentRagTargetState()));
  } catch (error) {
    // Browser storage can be disabled or full; rag still works without persistence.
  }
}

function readStoredAnydocsTargetState() {
  try {
    const raw = localStorage.getItem(ANYDOCS_TARGET_STORAGE_KEY);
    if (!raw) return {};
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function saveAnydocsTargetState() {
  try {
    localStorage.setItem(ANYDOCS_TARGET_STORAGE_KEY, JSON.stringify(currentAnydocsTargetState()));
  } catch (error) {
    // Browser storage can be disabled or full; integration still works without persistence.
  }
}

function applyStoredReadingTargetState() {
  const state = readStoredReadingTargetState();
  let applied = false;
  if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
    readingSourceDir = String(state.source_dir || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
    const outputRoot = String(state.output_root || "");
    if (outputRoot && $("reading_output_root")) {
      $("reading_output_root").value = outputRoot;
      if (outputRoot === $("run_output_root").value.trim()) {
        lastSyncedRunOutputRoot = outputRoot;
      }
      applied = true;
    }
  }
  return applied;
}

function applyStoredGraphTargetState() {
  const state = readStoredGraphTargetState();
  let applied = false;
  if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
    graphSourceDir = String(state.source_dir || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
    const outputRoot = String(state.output_root || "");
    if (outputRoot && $("graph_output_root")) {
      $("graph_output_root").value = outputRoot;
      if (
        outputRoot === $("reading_output_root").value.trim() ||
        outputRoot === $("run_output_root").value.trim()
      ) {
        lastSyncedGraphOutputRoot = outputRoot;
      }
      applied = true;
    }
  }
  return applied;
}

function applyStoredRagTargetState() {
  const state = readStoredRagTargetState();
  let applied = false;
  if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
    ragSourceDir = String(state.source_dir || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
    const outputRoot = String(state.output_root || "");
    if (outputRoot && $("rag_output_root")) {
      $("rag_output_root").value = outputRoot;
      if (
        outputRoot === $("reading_output_root").value.trim() ||
        outputRoot === $("run_output_root").value.trim()
      ) {
        lastSyncedRagOutputRoot = outputRoot;
      }
      applied = true;
    }
  }
  if (Object.prototype.hasOwnProperty.call(state, "vector_store_type") && $("rag_vector_store_type")) {
    $("rag_vector_store_type").value = String(state.vector_store_type || "local_jsonl");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "vector_store_url") && $("rag_vector_store_url")) {
    $("rag_vector_store_url").value = String(state.vector_store_url || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "vector_store_collection") && $("rag_vector_store_collection")) {
    $("rag_vector_store_collection").value = String(state.vector_store_collection || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "categories") && $("rag_categories")) {
    setSelectedValues("rag_categories", state.categories);
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redaction_panel_open") && $("rag_advanced_panel")) {
    $("rag_advanced_panel").open = !!state.redaction_panel_open;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redaction_enabled") && $("rag_redaction_enabled")) {
    $("rag_redaction_enabled").checked = !!state.redaction_enabled;
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redact_drop_matched_documents") && $("rag_redact_drop_matched_documents")) {
    $("rag_redact_drop_matched_documents").checked = !!state.redact_drop_matched_documents;
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redact_placeholder") && $("rag_redact_placeholder")) {
    $("rag_redact_placeholder").value = String(state.redact_placeholder || "[REDACTED]");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redact_terms") && $("rag_redact_terms")) {
    $("rag_redact_terms").value = String(state.redact_terms || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "redact_mappings") && $("rag_redact_mappings")) {
    $("rag_redact_mappings").value = String(state.redact_mappings || "");
    applied = true;
  }
  syncVectorStoreInputs();
  syncRagRedactionInputs();
  return applied;
}

function applyStoredAnydocsTargetState() {
  const state = readStoredAnydocsTargetState();
  let applied = false;
  if (Object.prototype.hasOwnProperty.call(state, "source_dir")) {
    anydocsSourceDir = String(state.source_dir || "");
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "output_root")) {
    const outputRoot = String(state.output_root || "");
    if (outputRoot && $("anydocs_output_root")) {
      $("anydocs_output_root").value = outputRoot;
      if (
        outputRoot === $("graph_output_root").value.trim() ||
        outputRoot === $("run_output_root").value.trim()
      ) {
        lastSyncedAnydocsOutputRoot = outputRoot;
      }
      applied = true;
    }
  }
  if (Object.prototype.hasOwnProperty.call(state, "anydocs_url") && $("anydocs_url")) {
    $("anydocs_url").value = String(state.anydocs_url || DEFAULT_ANYDOCS_URL);
    applied = true;
  }
  if (Object.prototype.hasOwnProperty.call(state, "bundle_min_quality")) {
    anydocsStandaloneBundleMinQuality = String(state.bundle_min_quality ?? "0");
    applied = true;
  }
  syncAnydocsBundleQualityInputs();
  refreshAnydocsBundlePath();
  return applied;
}

function syncGlobalOutputFrom(outputRoot) {
  const element = $("global_output_root");
  if (!element) return;
  const outputText = String(outputRoot || "");
  if (element.value !== outputText) element.value = outputText;
}

function sharedTargetStateFromTargets() {
  const candidates = [
    {source_dir: readingSourceDir, output_root: $("reading_output_root") ? $("reading_output_root").value.trim() : ""},
    {source_dir: graphSourceDir, output_root: $("graph_output_root") ? $("graph_output_root").value.trim() : ""},
    {source_dir: ragSourceDir, output_root: $("rag_output_root") ? $("rag_output_root").value.trim() : ""},
    {source_dir: anydocsSourceDir, output_root: $("anydocs_output_root") ? $("anydocs_output_root").value.trim() : ""},
    {source_dir: $("run_source_dir") ? $("run_source_dir").value.trim() : "", output_root: $("run_output_root") ? $("run_output_root").value.trim() : ""}
  ];
  return candidates.find(item => item.output_root) || {source_dir: "", output_root: ""};
}

function sharedOutputRootFromTargets() {
  return sharedTargetStateFromTargets().output_root;
}

function normalizeSharedTargetFromTargets({persist = false} = {}) {
  const target = sharedTargetStateFromTargets();
  if (target.output_root) setSharedTarget(target.source_dir, target.output_root, {persist});
  else syncGlobalOutputFrom("");
}

function setSharedTarget(sourceDir, outputRoot, {persist = true} = {}) {
  const sourceText = String(sourceDir || "");
  const outputText = String(outputRoot || "");
  readingSourceDir = sourceText;
  graphSourceDir = sourceText;
  ragSourceDir = sourceText;
  anydocsSourceDir = sourceText;
  for (const id of ["reading_output_root", "graph_output_root", "rag_output_root", "anydocs_output_root"]) {
    const element = $(id);
    if (element) element.value = outputText;
  }
  syncGlobalOutputFrom(outputText);
  if ($("run_output_root") && outputText === $("run_output_root").value.trim()) {
    lastSyncedRunOutputRoot = outputText;
  }
  lastSyncedGraphOutputRoot = outputText;
  lastSyncedRagOutputRoot = outputText;
  lastSyncedAnydocsOutputRoot = outputText;
  refreshAnydocsBundlePath();
  if (persist) {
    saveReadingTargetState();
    saveGraphTargetState();
    saveRagTargetState();
    saveAnydocsTargetState();
  }
}

function setReadingTarget(sourceDir, outputRoot, {persist = true} = {}) {
  setSharedTarget(sourceDir, outputRoot, {persist});
}

function setGraphTarget(sourceDir, outputRoot, {persist = true} = {}) {
  setSharedTarget(sourceDir, outputRoot, {persist});
}

function currentGraphTargetState() {
  return {
    source_dir: graphSourceDir,
    output_root: $("graph_output_root").value.trim()
  };
}

function setRagTarget(sourceDir, outputRoot, {persist = true} = {}) {
  setSharedTarget(sourceDir, outputRoot, {persist});
}

function setAnydocsTarget(sourceDir, outputRoot, {persist = true} = {}) {
  setSharedTarget(sourceDir, outputRoot, {persist});
}

function currentAnydocsTargetState() {
  return {
    source_dir: anydocsSourceDir,
    output_root: $("anydocs_output_root") ? $("anydocs_output_root").value.trim() : "",
    anydocs_url: $("anydocs_url") ? $("anydocs_url").value.trim() : DEFAULT_ANYDOCS_URL,
    bundle_min_quality: anydocsStandaloneBundleMinQuality
  };
}

function currentRagTargetState() {
  return {
    source_dir: ragSourceDir,
    output_root: $("rag_output_root").value.trim(),
    vector_store_type: $("rag_vector_store_type") ? $("rag_vector_store_type").value : "local_jsonl",
    vector_store_url: $("rag_vector_store_url") ? $("rag_vector_store_url").value.trim() : "",
    vector_store_collection: $("rag_vector_store_collection") ? $("rag_vector_store_collection").value.trim() : "",
    categories: selectedValues("rag_categories"),
    redaction_panel_open: $("rag_advanced_panel") ? $("rag_advanced_panel").open : false,
    redaction_enabled: $("rag_redaction_enabled") ? $("rag_redaction_enabled").checked : false,
    redact_drop_matched_documents: $("rag_redact_drop_matched_documents") ? $("rag_redact_drop_matched_documents").checked : false,
    redact_placeholder: $("rag_redact_placeholder") ? $("rag_redact_placeholder").value : "[REDACTED]",
    redact_terms: $("rag_redact_terms") ? $("rag_redact_terms").value : "",
    redact_mappings: $("rag_redact_mappings") ? $("rag_redact_mappings").value : ""
  };
}

function syncGraphTargetFrom(sourceDir, outputRoot, {force = false, syncAnydocs = true} = {}) {
  const outputText = String(outputRoot || "").trim();
  if (!outputText) return;
  const currentGraphOutput = $("graph_output_root").value.trim();
  const shouldSync = force || !currentGraphOutput || currentGraphOutput === lastSyncedGraphOutputRoot;
  if (!shouldSync) return;
  graphSourceDir = String(sourceDir || "");
  $("graph_output_root").value = outputText;
  syncGlobalOutputFrom(outputText);
  lastSyncedGraphOutputRoot = outputText;
  saveGraphTargetState();
  if (syncAnydocs) syncAnydocsTargetFrom(sourceDir, outputRoot, {force});
}

function syncGraphTargetFromReadingOutput({force = false, syncAnydocs = true} = {}) {
  const paths = readingPathPayload();
  syncGraphTargetFrom(paths.source_dir, paths.output_root, {force, syncAnydocs});
}

function syncRagTargetFrom(sourceDir, outputRoot, {force = false} = {}) {
  const outputText = String(outputRoot || "").trim();
  if (!outputText) return;
  const currentRagOutput = $("rag_output_root").value.trim();
  const shouldSync = force || !currentRagOutput || currentRagOutput === lastSyncedRagOutputRoot;
  if (!shouldSync) return;
  ragSourceDir = String(sourceDir || "");
  $("rag_output_root").value = outputText;
  syncGlobalOutputFrom(outputText);
  lastSyncedRagOutputRoot = outputText;
  saveRagTargetState();
}

function syncAnydocsTargetFrom(sourceDir, outputRoot, {force = false} = {}) {
  const outputText = String(outputRoot || "").trim();
  if (!outputText || !$("anydocs_output_root")) return;
  const currentOutput = $("anydocs_output_root").value.trim();
  const shouldSync = force || !currentOutput || currentOutput === lastSyncedAnydocsOutputRoot;
  if (!shouldSync) return;
  anydocsSourceDir = String(sourceDir || "");
  $("anydocs_output_root").value = outputText;
  syncGlobalOutputFrom(outputText);
  lastSyncedAnydocsOutputRoot = outputText;
  refreshAnydocsBundlePath();
  saveAnydocsTargetState();
}

function syncAnydocsTargetFromGraphOutput({force = false} = {}) {
  const paths = graphPathPayload();
  syncAnydocsTargetFrom(paths.source_dir, paths.output_root, {force});
}

function syncRagTargetFromReadingOutput({force = false} = {}) {
  const paths = readingPathPayload();
  syncRagTargetFrom(paths.source_dir, paths.output_root, {force});
}

function syncReadingTargetFromRunOutput({force = false, syncGraph = true, syncAnydocs = true} = {}) {
  const sourceDir = $("run_source_dir").value.trim();
  const outputRoot = $("run_output_root").value.trim();
  if (!outputRoot) return;
  const currentReadingOutput = $("reading_output_root").value.trim();
  const shouldSync = force || !currentReadingOutput || currentReadingOutput === lastSyncedRunOutputRoot;
  if (!shouldSync) return;
  readingSourceDir = sourceDir;
  $("reading_output_root").value = outputRoot;
  syncGlobalOutputFrom(outputRoot);
  lastSyncedRunOutputRoot = outputRoot;
  saveReadingTargetState();
  if (syncGraph) syncGraphTargetFrom(sourceDir, outputRoot, {force, syncAnydocs});
  syncRagTargetFrom(sourceDir, outputRoot, {force});
}

function syncReadingSourceFromRunIfLinked() {
  const runOutputRoot = $("run_output_root").value.trim();
  const readingOutputRoot = $("reading_output_root").value.trim();
  if (readingOutputRoot && readingOutputRoot !== runOutputRoot && readingOutputRoot !== lastSyncedRunOutputRoot) return;
  readingSourceDir = $("run_source_dir").value.trim();
  saveReadingTargetState();
  syncGraphTargetFrom(readingSourceDir, readingOutputRoot || runOutputRoot);
  syncRagTargetFrom(readingSourceDir, readingOutputRoot || runOutputRoot);
  syncAnydocsTargetFrom(readingSourceDir, readingOutputRoot || runOutputRoot);
}

function syncSharedTargetFromGlobalInput({persist = true} = {}) {
  const outputRoot = $("global_output_root") ? $("global_output_root").value.trim() : "";
  readingSourceDir = "";
  graphSourceDir = "";
  ragSourceDir = "";
  anydocsSourceDir = "";
  for (const id of ["reading_output_root", "graph_output_root", "rag_output_root", "anydocs_output_root"]) {
    const element = $(id);
    if (element) element.value = outputRoot;
  }
  refreshAnydocsBundlePath();
  if (persist) {
    saveReadingTargetState();
    saveGraphTargetState();
    saveRagTargetState();
    saveAnydocsTargetState();
  }
}

async function applySharedOutput({showError = true} = {}) {
  const outputRoot = $("global_output_root") ? $("global_output_root").value.trim() : "";
  if (!outputRoot) {
    syncSharedTargetFromGlobalInput();
    clearReadingRows();
    clearGraphState("graph_need_paths");
    clearRagState("rag_need_output");
    refreshAnydocsBundlePath();
    return null;
  }
  syncSharedTargetFromGlobalInput();
  const response = await fetch("/api/reading-output", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({output_root: outputRoot})
  });
  const payload = await response.json();
  if (!response.ok) {
    if (showError) showToast(payload.error || tr("reading_output_apply_failed"));
    return null;
  }
  setSharedTarget(payload.source_dir || "", payload.output_root || outputRoot);
  if ($("section-reading").classList.contains("active")) await loadRows();
  if ($("section-graph").classList.contains("active")) await loadGraph();
  if ($("section-rag").classList.contains("active")) await loadRagStatus();
  refreshAnydocsBundlePath();
  return payload;
}

function applyStoredRunFormState() {
  const state = readStoredRunFormState();
  const applyCheckboxState = Number(state._version || 0) === RUN_FORM_STORAGE_VERSION;
  for (const id of [...RUN_FORM_VALUE_FIELDS, ...GRAPH_FORM_VALUE_FIELDS]) {
    if (!Object.prototype.hasOwnProperty.call(state, id)) continue;
    const element = $(id);
    if (!element) continue;
    const value = String(state[id] ?? "");
    if (!value && !RUN_FORM_ALLOW_EMPTY_FIELDS.has(id) && !GRAPH_FORM_ALLOW_EMPTY_FIELDS.has(id)) continue;
    element.value = value;
  }
  if (!applyCheckboxState) return;
  for (const id of RUN_FORM_CHECKBOX_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(state, id)) continue;
    const element = $(id);
    if (element) element.checked = !!state[id];
  }
}

function initRunFormPersistence() {
  for (const id of [...RUN_FORM_VALUE_FIELDS, ...GRAPH_FORM_VALUE_FIELDS, ...RUN_FORM_SECRET_FIELDS, ...RUN_FORM_CHECKBOX_FIELDS]) {
    const element = $(id);
    if (!element) continue;
    const eventName = element.tagName === "INPUT" && element.type !== "checkbox" ? "input" : "change";
    element.addEventListener(eventName, () => {
      if (id === "run_output_root") syncReadingTargetFromRunOutput({force: true});
      if (id === "run_source_dir") syncReadingSourceFromRunIfLinked();
      saveRunFormState();
    });
  }
  for (const id of ["run_source_dir", "run_output_root"]) {
    const element = $(id);
    if (element) element.addEventListener("blur", () => autoApplyPaths());
  }
}

function initReadingTargetPersistence() {
  const element = $("reading_output_root");
  if (!element) return;
  element.addEventListener("input", () => {
    readingSourceDir = "";
    saveReadingTargetState();
    syncGraphTargetFrom("", element.value.trim(), {force: true});
    syncRagTargetFrom("", element.value.trim(), {force: true});
  });
  element.addEventListener("blur", () => autoApplyReadingOutput());
}

function initSharedTargetPersistence() {
  const element = $("global_output_root");
  if (!element) return;
  element.addEventListener("input", () => syncSharedTargetFromGlobalInput());
  element.addEventListener("blur", () => applySharedOutput());
}

function initGraphTargetPersistence() {
  const element = $("graph_output_root");
  if (!element) return;
  element.addEventListener("input", () => {
    graphSourceDir = "";
    saveGraphTargetState();
  });
  element.addEventListener("blur", () => autoApplyGraphOutput());
}

function initRagTargetPersistence() {
  const outputElement = $("rag_output_root");
  if (outputElement) {
    outputElement.addEventListener("input", () => {
      ragSourceDir = "";
      saveRagTargetState();
    });
  }
  const typeElement = $("rag_vector_store_type");
  if (typeElement) {
    typeElement.addEventListener("change", () => {
      syncVectorStoreInputs();
      saveRagTargetState();
    });
  }
  for (const id of ["rag_vector_store_url", "rag_vector_store_collection"]) {
    const element = $(id);
    if (!element) continue;
    element.addEventListener("input", () => saveRagTargetState());
  }
  const categoriesElement = $("rag_categories");
  if (categoriesElement) {
    categoriesElement.addEventListener("change", () => saveRagTargetState());
  }
  const advancedPanel = $("rag_advanced_panel");
  if (advancedPanel) advancedPanel.addEventListener("toggle", () => saveRagTargetState());
  const redactionEnabled = $("rag_redaction_enabled");
  if (redactionEnabled) {
    redactionEnabled.addEventListener("change", () => {
      syncRagRedactionInputs();
      saveRagTargetState();
    });
  }
  for (const id of ["rag_redact_drop_matched_documents", "rag_redact_placeholder", "rag_redact_terms", "rag_redact_mappings"]) {
    const element = $(id);
    if (!element) continue;
    const eventName = element.type === "checkbox" ? "change" : "input";
    element.addEventListener(eventName, () => saveRagTargetState());
  }
  syncVectorStoreInputs();
  syncRagRedactionInputs();
}

function initAnydocsTargetPersistence() {
  const outputElement = $("anydocs_output_root");
  if (outputElement) {
    outputElement.addEventListener("input", () => {
      anydocsSourceDir = "";
      refreshAnydocsBundlePath();
      saveAnydocsTargetState();
    });
  }
  const urlElement = $("anydocs_url");
  if (urlElement) {
    urlElement.addEventListener("input", () => saveAnydocsTargetState());
  }
  const qualityElement = $("anydocs_bundle_min_quality");
  const qualityNumberElement = $("anydocs_bundle_min_quality_number");
  if (qualityElement) {
    qualityElement.addEventListener("input", () => {
      if (qualityNumberElement) qualityNumberElement.value = qualityElement.value;
      anydocsStandaloneBundleMinQuality = qualityElement.value || "0";
      updateAnydocsQualitySliderVisual();
      saveAnydocsTargetState();
      renderAnydocsStats();
    });
  }
  if (qualityNumberElement) {
    qualityNumberElement.addEventListener("input", () => {
      const value = normalizeQualityScore(qualityNumberElement.value);
      qualityNumberElement.value = String(value);
      if (qualityElement) qualityElement.value = String(value);
      anydocsStandaloneBundleMinQuality = String(value);
      updateAnydocsQualitySliderVisual();
      saveAnydocsTargetState();
      renderAnydocsStats();
    });
  }
  updateAnydocsQualitySliderVisual();
}

function syncAnydocsBundleQualityInputs() {
  const qualityElement = $("anydocs_bundle_min_quality");
  const qualityNumberElement = $("anydocs_bundle_min_quality_number");
  if (!qualityElement) return;
  const value = normalizeQualityScore(anydocsStandaloneBundleMinQuality);
  qualityElement.value = String(value);
  if (qualityNumberElement) {
    qualityNumberElement.value = String(value);
  }
  updateAnydocsQualitySliderVisual();
}

function updateAnydocsQualitySliderVisual() {
  const qualityElement = $("anydocs_bundle_min_quality");
  if (!qualityElement) return;
  const value = normalizeQualityScore(qualityElement.value);
  qualityElement.style.setProperty("--quality-progress", value + "%");
}

function setUiLanguage(language) {
  uiLanguage = I18N[language] ? language : "zh-CN";
  localStorage.setItem("doctriage_ui_language", uiLanguage);
  applyI18n();
}

function applyI18n() {
  document.documentElement.lang = uiLanguage;
  if ($("ui_language")) $("ui_language").value = uiLanguage;
  document.querySelectorAll("[data-i18n]").forEach(item => {
    item.textContent = tr(item.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(item => {
    item.setAttribute("placeholder", tr(item.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-tip]").forEach(item => {
    item.dataset.tip = tr(item.dataset.i18nTip);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(item => {
    item.title = tr(item.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach(item => {
    item.setAttribute("aria-label", tr(item.dataset.i18nAriaLabel));
  });
  if ($("reading_scope")) $("reading_scope").value = readingScope;
  renderStatsFromRows(filteredRows, allRows.length);
  renderPager();
  renderRows(currentRows);
  if (hasGraphPayload()) {
    renderGraphStats(graphMeta);
    renderGraphTaskStats(graphMeta);
    if (graphClusterData) renderGraphCluster();
    else if (filteredGraphClusters.length) renderGraphClusterList();
    else renderGraphEmptyState();
  } else {
    renderClearedGraphState();
  }
  if (hasRagPayload()) {
    renderRagStatus(ragMeta);
    if (ragSearchPayload) renderRagResults(ragSearchPayload);
  }
  renderAnydocsStats();
  renderAnydocsOpenStatus();
  syncVectorStoreInputs();
}

function switchTab(name) {
  for (const id of ["analysis", "reading", "graph", "rag", "agents"]) {
    $("tab-" + id).classList.toggle("active", id === name);
    $("section-" + id).classList.toggle("active", id === name);
  }
  const sharedTargetPanel = $("shared_target_panel");
  if (sharedTargetPanel) sharedTargetPanel.hidden = name === "analysis";
  const readingFilterPanel = $("reading_filter_panel");
  if (readingFilterPanel) readingFilterPanel.hidden = name !== "reading";
  syncGlobalOutputFrom(sharedOutputRootFromTargets());
  if (name === "analysis") loadAnalysis();
  if (name === "reading") loadReadingRowsIfReady();
  if (name === "graph") {
    if (graphPathPayload().output_root) loadGraph();
    else clearGraphState("graph_need_paths");
  }
  if (name === "rag") {
    if (ragPathPayload().output_root) loadRagStatus();
    else clearRagState("rag_need_output");
  }
  if (name === "agents") {
    refreshAnydocsBundlePath();
    loadAnydocsQualityStats();
  }
  localStorage.setItem("doctriage_tab", name);
}

function loadReadingRowsIfReady() {
  if (!$("section-reading").classList.contains("active")) return;
  if (!readingPathPayload().output_root) return;
  const key = readingRowsCacheKey();
  if (key === readingRowsLoadedKey || key === readingRowsLoadingKey) return;
  loadRows();
}

function readingRowsCacheKey() {
  const paths = readingPathPayload();
  return [readingScope, paths.source_dir || "", paths.output_root || ""].join("\u0000");
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const payload = await response.json();
  if (!response.ok) return;
  capabilities = payload.capabilities || {};
  configuredEmbeddingEndpoint = payload.embedding_endpoint || DEFAULT_EMBEDDING_ENDPOINT;
  $("run_source_dir").value = payload.source_dir || "";
  $("run_output_root").value = payload.output_root || "";
  $("reading_output_root").value = payload.output_root || "";
  $("graph_output_root").value = payload.output_root || "";
  $("rag_output_root").value = payload.output_root || "";
  $("anydocs_output_root").value = payload.output_root || "";
  syncGlobalOutputFrom(payload.output_root || "");
  readingSourceDir = payload.source_dir || "";
  lastSyncedRunOutputRoot = payload.output_root || "";
  lastAppliedRunPathKey = runPathKey(payload.source_dir || "", payload.output_root || "");
  graphSourceDir = payload.source_dir || "";
  lastSyncedGraphOutputRoot = payload.output_root || "";
  ragSourceDir = payload.source_dir || "";
  lastSyncedRagOutputRoot = payload.output_root || "";
  anydocsSourceDir = payload.source_dir || "";
  lastSyncedAnydocsOutputRoot = payload.output_root || "";
  applyStoredRunFormState();
  const readingApplied = applyStoredReadingTargetState();
  const graphApplied = applyStoredGraphTargetState();
  const ragApplied = applyStoredRagTargetState();
  const anydocsApplied = applyStoredAnydocsTargetState();
  if (!readingApplied) syncReadingTargetFromRunOutput({force: true, syncGraph: !graphApplied, syncAnydocs: !anydocsApplied});
  if (!graphApplied) syncGraphTargetFromReadingOutput({force: true, syncAnydocs: !anydocsApplied});
  if (!ragApplied) syncRagTargetFromReadingOutput({force: true});
  if (!anydocsApplied) syncAnydocsTargetFromGraphOutput({force: true});
  normalizeSharedTargetFromTargets({persist: true});
  for (const id of ["pick_source_btn", "pick_output_btn", "pick_global_output_btn"]) {
    if ($(id)) {
      $(id).disabled = capabilities.folder_picker === false;
      $(id).title = capabilities.folder_picker === false ? tr("folder_picker_unavailable") : "";
    }
  }
  renderUploadStats();
  if (capabilities.headless_hint) {
    showToast(capabilities.headless_hint);
  }
  applyI18n();
  loadAnalysis();
  loadReadingRowsIfReady();
}

async function pickFolder(targetId) {
  const response = await fetch("/api/pick-folder", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({target: targetId})
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("pick_failed"));
  if (payload.path) $(targetId).value = payload.path;
  if (targetId === "global_output_root") {
    await applySharedOutput();
    return;
  }
  if (targetId === "run_output_root") syncReadingTargetFromRunOutput({force: true});
  if (targetId === "run_source_dir") syncReadingSourceFromRunIfLinked();
  if (targetId.startsWith("run_")) saveRunFormState();
  if (targetId === "run_source_dir" || targetId === "run_output_root") autoApplyPaths();
  if (targetId === "reading_output_root") {
    readingSourceDir = "";
    saveReadingTargetState();
    syncGraphTargetFrom("", payload.path || "", {force: true});
    await applyReadingOutput();
  }
  if (targetId === "graph_output_root") {
    graphSourceDir = "";
    saveGraphTargetState();
    await applyGraphOutput();
  }
  if (targetId === "rag_output_root") {
    ragSourceDir = "";
    saveRagTargetState();
  }
  if (targetId === "anydocs_output_root") {
    anydocsSourceDir = "";
    refreshAnydocsBundlePath();
    saveAnydocsTargetState();
  }
}

function runPathKey(sourceDir, outputRoot) {
  return `${String(sourceDir || "").trim()}\n${String(outputRoot || "").trim()}`;
}

async function autoApplyPaths() {
  const sourceDir = $("run_source_dir").value.trim();
  const outputRoot = $("run_output_root").value.trim();
  if (!sourceDir || !outputRoot) return;
  const key = runPathKey(sourceDir, outputRoot);
  if (key === lastAppliedRunPathKey) return;
  await applyPaths({showSuccess: false});
}

async function applyPaths({showSuccess = true} = {}) {
  saveRunFormState();
  const sourceDir = $("run_source_dir").value.trim();
  const outputRoot = $("run_output_root").value.trim();
  const response = await fetch("/api/paths", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      source_dir: sourceDir,
      output_root: outputRoot
    })
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("paths_apply_failed"));
  lastAppliedRunPathKey = runPathKey(sourceDir, outputRoot);
  syncReadingTargetFromRunOutput({force: true});
  if (showSuccess) showToast(tr("paths_applied"));
  loadAnalysis();
  loadRows();
  if ($("section-graph").classList.contains("active")) loadGraph();
  if ($("section-rag").classList.contains("active")) loadRagStatus();
}

async function autoApplyReadingOutput() {
  const outputRoot = $("reading_output_root").value.trim();
  if (!outputRoot) {
    readingSourceDir = "";
    saveReadingTargetState();
    syncGraphTargetFrom("", "", {force: true});
    syncRagTargetFrom("", "", {force: true});
    renderReadingError(tr("need_reading_output"));
    return null;
  }
  return applyReadingOutput();
}

async function applyReadingOutput() {
  const outputRoot = $("reading_output_root").value.trim();
  if (!outputRoot) {
    renderReadingError(tr("need_reading_output"));
    return null;
  }
  const response = await fetch("/api/reading-output", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({output_root: outputRoot})
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload.error || tr("reading_output_apply_failed");
    showToast(message);
    renderReadingError(message);
    return null;
  }
  setReadingTarget(payload.source_dir || "", payload.output_root || outputRoot);
  await loadRows();
  if ($("section-graph").classList.contains("active")) loadGraph();
  if ($("section-rag").classList.contains("active")) loadRagStatus();
  return payload;
}

async function autoApplyGraphOutput() {
  const outputRoot = $("graph_output_root").value.trim();
  if (!outputRoot) {
    graphSourceDir = "";
    saveGraphTargetState();
    clearGraphState("graph_need_paths");
    return null;
  }
  return applyGraphOutput();
}

async function applyGraphOutput() {
  const outputRoot = $("graph_output_root").value.trim();
  if (!outputRoot) {
    clearGraphState("graph_need_paths");
    return null;
  }
  const response = await fetch("/api/graph-output", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({output_root: outputRoot})
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload.error || tr("graph_output_apply_failed");
    showToast(message);
    renderGraphError(message);
    return null;
  }
  setGraphTarget(payload.source_dir || "", payload.output_root || outputRoot);
  return loadGraph();
}

function runPayload() {
  const llmEndpoint = $("run_llm_endpoint").value.trim();
  const uploadId = currentUploadWorkspace?.complete ? currentUploadWorkspace.upload_id : "";
  return {
    source_dir: $("run_source_dir").value.trim(),
    output_root: $("run_output_root").value.trim(),
    upload_id: uploadId,
    llm_endpoint: llmEndpoint,
    llm_model: $("run_llm_model").value.trim(),
    llm_api_key: $("run_llm_api_key") ? $("run_llm_api_key").value.trim() : "",
    output_language: $("run_output_language").value,
    embedding_endpoint: inferEmbeddingEndpoint(llmEndpoint),
    embedding_model: "",
    embedding_api_key: $("run_embedding_api_key") ? $("run_embedding_api_key").value.trim() : "",
    concurrency: $("run_concurrency").value,
    limit: $("run_limit").value,
    max_file_size_mb: $("run_max_file_size_mb").value,
    quality_threshold: $("run_quality_threshold").value,
    timeout_seconds: $("run_timeout_seconds").value,
    plan_only: $("run_plan_only").checked,
    ocr_enabled: $("run_ocr_enabled").checked,
    no_ocr: !$("run_ocr_enabled").checked,
    manifest_analysis: false,
    skip_manifest_analysis: true,
    force_reprocess: false,
    content_hash: false,
    mine_relationships: false,
    relationship_use_text_citations: false,
    relationship_use_embeddings: false
  };
}

function graphRelationshipPayload() {
  const embeddingModel = $("run_embedding_model") ? $("run_embedding_model").value.trim() : "";
  const payload = {
    ...runPayload(),
    ...graphPathPayload()
  };
  payload.embedding_model = embeddingModel;
  payload.mine_relationships = true;
  payload.relationship_use_text_citations = true;
  payload.relationship_use_embeddings = !!embeddingModel;
  return payload;
}

function validateEmbeddingModelSelection(payload) {
  if (!payload || !payload.relationship_use_embeddings) return true;
  if (String(payload.embedding_model || "").trim()) return true;
  showToast(tr("embedding_model_required"));
  return false;
}

function inferEmbeddingEndpoint(llmEndpoint) {
  const endpoint = String(llmEndpoint || "").trim();
  const configured = String(configuredEmbeddingEndpoint || "").trim();
  if (configured && configured !== DEFAULT_EMBEDDING_ENDPOINT) return configured;
  if (/\/api\/(generate|chat)\/?$/i.test(endpoint)) {
    return endpoint.replace(/\/api\/(generate|chat)\/?$/i, "/api/embeddings");
  }
  if (/\/v1\/chat\/completions\/?$/i.test(endpoint)) {
    return endpoint.replace(/\/v1\/chat\/completions\/?$/i, "/v1/embeddings");
  }
  if (/\/api\/(embed|embeddings)\/?$/i.test(endpoint)) {
    return endpoint;
  }
  if (/\/v1\/embeddings\/?$/i.test(endpoint)) {
    return endpoint;
  }
  return configuredEmbeddingEndpoint || DEFAULT_EMBEDDING_ENDPOINT;
}

function formatLlmCheckMessage(payload) {
  if (!payload) return tr("llm_check_failed");
  const parts = [];
  if (payload.provider) parts.push(String(payload.provider));
  if (payload.status_code) parts.push(`HTTP ${payload.status_code}`);
  if (payload.message) parts.push(String(payload.message));
  return parts.join(" · ") || tr("llm_check_failed");
}

async function ensureEndpointReady(_requestPayload, {role = "analysis", endpoint = "", model = ""} = {}) {
  const probePayload = {
    role,
    endpoint,
    model
  };
  if (role === "embedding" && _requestPayload && _requestPayload.embedding_api_key) {
    probePayload.embedding_api_key = _requestPayload.embedding_api_key;
  }
  if (_requestPayload && _requestPayload.llm_api_key) {
    probePayload.llm_api_key = _requestPayload.llm_api_key;
  }
  const response = await fetch("/api/test/llm", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(probePayload)
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    showToast(formatLlmCheckMessage(payload));
    return false;
  }
  return true;
}

function openUploadDialog() {
  const dialog = $("upload_dialog");
  if (!dialog) return;
  renderUploadStats();
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function closeUploadDialog() {
  const dialog = $("upload_dialog");
  if (!dialog) return;
  closeUploadSourceMenu();
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

function setUploadSourceMenuOpen(open) {
  const menu = $("upload_source_menu");
  const button = $("pick_upload_btn");
  if (menu) menu.hidden = !open;
  if (button) button.setAttribute("aria-expanded", open ? "true" : "false");
}

function closeUploadSourceMenu() {
  setUploadSourceMenuOpen(false);
}

function toggleUploadSourceMenu(event) {
  if (uploadBusy) return;
  if (event) event.stopPropagation();
  const menu = $("upload_source_menu");
  setUploadSourceMenuOpen(!menu || menu.hidden);
}

function pickUploadFiles() {
  closeUploadSourceMenu();
  const input = $("upload_files_input");
  if (!input || uploadBusy) return;
  input.value = "";
  input.click();
}

function pickUploadFolder() {
  closeUploadSourceMenu();
  const input = $("upload_folder_input");
  if (!input || uploadBusy) return;
  input.value = "";
  input.click();
}

function initUploadControls() {
  const fileInput = $("upload_files_input");
  if (fileInput) fileInput.addEventListener("change", () => uploadSelectedFiles(fileInput.files, {folder: false}));
  const folderInput = $("upload_folder_input");
  if (folderInput) folderInput.addEventListener("change", () => uploadSelectedFiles(folderInput.files, {folder: true}));
  document.addEventListener("click", closeUploadSourceMenu);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeUploadSourceMenu();
  });
  const dialog = $("upload_dialog");
  if (dialog) {
    dialog.addEventListener("click", event => {
      if (event.target === dialog) closeUploadDialog();
    });
  }
  renderUploadStats();
}

async function ensureUploadWorkspace() {
  if (currentUploadWorkspace && currentUploadWorkspace.upload_id) return currentUploadWorkspace;
  renderUploadStats(tr("upload_creating"));
  const response = await fetch("/api/uploads", {method: "POST"});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || tr("upload_failed"));
  currentUploadWorkspace = payload;
  return payload;
}

function uploadRelativePath(file, {folder = false, rootAliases = new Map()} = {}) {
  const rawPath = folder && file.webkitRelativePath ? file.webkitRelativePath : file.name;
  const normalized = String(rawPath || file.name || "upload.bin").replace(/\\/g, "/").replace(/^\/+/, "");
  if (!folder || !normalized.includes("/")) return normalized;
  const parts = normalized.split("/");
  parts[0] = rootAliases.get(parts[0]) || parts[0];
  return parts.join("/");
}

function buildFolderRootAliases(fileList) {
  const existingRoots = new Set(currentUploadWorkspace?.roots || []);
  const aliases = new Map();
  for (const file of Array.from(fileList || [])) {
    const relativePath = String(file.webkitRelativePath || "").replace(/\\/g, "/").replace(/^\/+/, "");
    const root = relativePath.includes("/") ? relativePath.split("/", 1)[0] : "";
    if (!root || aliases.has(root)) continue;
    let alias = root;
    let suffix = 2;
    while (existingRoots.has(alias)) {
      alias = `${root} (${suffix})`;
      suffix += 1;
    }
    aliases.set(root, alias);
    existingRoots.add(alias);
  }
  return aliases;
}

async function uploadSelectedFiles(fileList, {folder = false} = {}) {
  const files = Array.from(fileList || []);
  if (!files.length) return showToast(tr("upload_no_files"));
  uploadBusy = true;
  updateUploadButtons();
  if ($("uploadBar")) $("uploadBar").style.width = "0%";
  try {
    const workspace = await ensureUploadWorkspace();
    const rootAliases = folder ? buildFolderRootAliases(files) : new Map();
    renderUploadStats(trf("upload_started", {count: files.length}));
    let uploaded = 0;
    let uploadedBytes = 0;
    for (const file of files) {
      const relativePath = uploadRelativePath(file, {folder, rootAliases});
      const response = await fetch(`/api/uploads/${workspace.upload_id}/files?relative_path=${encodeURIComponent(relativePath)}`, {
        method: "POST",
        headers: {"Content-Type": "application/octet-stream"},
        body: file
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || tr("upload_failed"));
      currentUploadWorkspace = payload;
      uploaded += 1;
      uploadedBytes += Number(file.size || payload.size || 0);
      const percent = Math.round((uploaded / files.length) * 100);
      if ($("uploadBar")) $("uploadBar").style.width = `${percent}%`;
      renderUploadStats(`${uploaded}/${files.length} · ${formatBytes(uploadedBytes)}`);
    }
    const completed = await completeUploadWorkspace();
    showToast(trf("upload_complete", {count: completed.file_count || files.length, size: formatBytes(completed.total_bytes || uploadedBytes)}));
  } catch (error) {
    showToast(error.message || tr("upload_failed"));
  } finally {
    uploadBusy = false;
    updateUploadButtons();
    renderUploadStats();
  }
}

async function completeUploadWorkspace() {
  const workspace = await ensureUploadWorkspace();
  const response = await fetch(`/api/uploads/${workspace.upload_id}/complete`, {method: "POST"});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || tr("upload_failed"));
  currentUploadWorkspace = payload;
  if ($("uploadBar")) $("uploadBar").style.width = "100%";
  return payload;
}

async function clearUploadWorkspace() {
  if (!currentUploadWorkspace || !currentUploadWorkspace.upload_id || uploadBusy) {
    currentUploadWorkspace = null;
    if ($("uploadBar")) $("uploadBar").style.width = "0%";
    renderUploadStats();
    return;
  }
  const uploadId = currentUploadWorkspace.upload_id;
  const response = await fetch(`/api/uploads/${uploadId}`, {method: "DELETE"});
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("upload_failed"));
  currentUploadWorkspace = null;
  if ($("uploadBar")) $("uploadBar").style.width = "0%";
  renderUploadStats();
  showToast(tr("upload_cleared"));
}

function updateUploadButtons() {
  for (const id of ["open_upload_dialog_btn", "pick_upload_btn", "pick_upload_files_btn", "pick_upload_folder_btn", "clear_upload_workspace_btn"]) {
    const button = $(id);
    if (button) button.disabled = uploadBusy;
  }
}

function renderUploadStats(message = "") {
  const target = $("uploadStats");
  if (!target) return;
  const parts = [];
  if (message) parts.push(message);
  if (currentUploadWorkspace && currentUploadWorkspace.upload_id) {
    parts.push(`ID ${currentUploadWorkspace.upload_id.slice(0, 8)}`);
    parts.push(`${tr("documents_unit")} ${Number(currentUploadWorkspace.file_count || 0)}`);
    if (Number(currentUploadWorkspace.root_count || 0) > 0) {
      parts.push(`${tr("folders_unit")} ${Number(currentUploadWorkspace.root_count)}`);
    }
    parts.push(formatBytes(currentUploadWorkspace.total_bytes || 0));
  } else {
    parts.push(tr("upload_empty"));
  }
  target.innerHTML = parts.map(item => `<span class="pill">${escapeHtml(item)}</span>`).join("");
  const clearButton = $("clear_upload_workspace_btn");
  if (clearButton) {
    clearButton.disabled = uploadBusy || !currentUploadWorkspace?.upload_id;
  }
}

function formatBytes(value) {
  const bytes = Math.max(0, Number(value || 0));
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${Math.floor(bytes)} B`;
}

function renderVectorStoreTestStats(payload) {
  const parts = [
    payload.ok ? tr("vector_store_ok") : tr("vector_store_unavailable"),
    payload.reachable ? tr("vector_store_reachable") : "",
    payload.store_type ? String(payload.store_type) : "",
    payload.status_code ? `HTTP ${payload.status_code}` : "",
    payload.collection_checked
      ? (payload.collection_exists ? tr("vector_store_collection_exists") : tr("vector_store_collection_missing"))
      : "",
    payload.vector_count !== undefined ? `${tr("vector_store_vectors")} ${Number(payload.vector_count || 0)}` : "",
    payload.vector_dimension ? `Dim ${Number(payload.vector_dimension)}` : "",
    payload.message ? String(payload.message) : ""
  ].filter(Boolean);
  $("vectorStoreTestStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
}

async function testVectorStore() {
  const requestPayload = vectorStorePayload();
  if (["local_jsonl", "qdrant_local"].includes(requestPayload.store_type) && !requestPayload.output_root) {
    return showToast(tr("rag_need_output"));
  }
  saveRagTargetState();
  $("test_vector_store_btn").disabled = true;
  $("vectorStoreTestStats").innerHTML = `<span class="pill">${escapeHtml(tr("testing_vector_store"))}</span>`;
  const response = await fetch("/api/test/vector-store", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(requestPayload)
  });
  const payload = await response.json();
  $("test_vector_store_btn").disabled = false;
  if (!response.ok) {
    $("vectorStoreTestStats").innerHTML = "";
    return showToast(payload.error || tr("vector_store_test_failed"));
  }
  renderVectorStoreTestStats(payload);
}

function pathPayload() {
  const uploadedSource = currentUploadWorkspace?.complete
    ? String(currentUploadWorkspace.source_dir || "").trim()
    : "";
  return {
    source_dir: $("run_source_dir").value.trim() || uploadedSource,
    output_root: $("run_output_root").value.trim()
  };
}

function readingPathPayload() {
  const sourceDir = readingSourceDir;
  const outputRoot = $("reading_output_root").value.trim() || $("run_output_root").value.trim();
  return {
    source_dir: sourceDir,
    output_root: outputRoot
  };
}

function graphPathPayload() {
  const sourceDir = graphSourceDir;
  const outputRoot = $("graph_output_root").value.trim();
  return {
    source_dir: sourceDir,
    output_root: outputRoot
  };
}

function ragPathPayload() {
  const sourceDir = ragSourceDir;
  const outputRoot = $("rag_output_root").value.trim();
  return {
    source_dir: sourceDir,
    output_root: outputRoot
  };
}

function anydocsPathPayload() {
  const outputRoot = $("anydocs_output_root").value.trim() || $("graph_output_root").value.trim() || $("run_output_root").value.trim();
  let sourceDir = anydocsSourceDir;
  if (!sourceDir && outputRoot) {
    if (outputRoot === $("graph_output_root").value.trim()) sourceDir = graphSourceDir;
    else if (outputRoot === $("reading_output_root").value.trim()) sourceDir = readingSourceDir;
    else if (outputRoot === $("run_output_root").value.trim()) sourceDir = $("run_source_dir").value.trim();
  }
  return {
    source_dir: sourceDir,
    output_root: outputRoot
  };
}

function anydocsBundlePath() {
  const outputRoot = anydocsPathPayload().output_root;
  if (!outputRoot) return "";
  const separator = outputRoot.includes("/") && !outputRoot.includes("\\") ? "/" : "\\";
  return outputRoot.replace(/[\\\/]+$/, "") + separator + "_relationships" + separator + "doctriage_bundle.json";
}

function refreshAnydocsBundlePath() {
  if ($("anydocs_bundle_path")) $("anydocs_bundle_path").value = anydocsBundlePath();
  renderAnydocsStats();
}

function ragPayload() {
  const selectedVectorStore = $("rag_vector_store_type") ? $("rag_vector_store_type").value : "local_jsonl";
  const ragVectorStore = selectedVectorStore === "qdrant_local" ? "qdrant_local" : "local_jsonl";
  return {
    ...runPayload(),
    ...ragPathPayload(),
    embedding_endpoint: inferEmbeddingEndpoint($("run_llm_endpoint").value.trim()),
    embedding_model: $("rag_embedding_model").value.trim(),
    rag_min_quality: $("rag_min_quality").value,
    rag_categories: selectedValues("rag_categories").join(","),
    rag_limit: $("rag_limit").value,
    rag_chunk_max_chars: $("rag_chunk_max_chars").value,
    rag_chunk_overlap_chars: $("rag_chunk_overlap_chars").value,
    rag_vector_store_type: ragVectorStore,
    rag_qdrant_path: ragVectorStore === "qdrant_local" && $("rag_vector_store_url") ? $("rag_vector_store_url").value.trim() : "",
    rag_qdrant_collection: $("rag_vector_store_collection") ? $("rag_vector_store_collection").value.trim() || "doctriage_rag" : "doctriage_rag",
    rag_redaction_enabled: $("rag_redaction_enabled") ? $("rag_redaction_enabled").checked : false,
    rag_redact_drop_matched_documents: $("rag_redact_drop_matched_documents") ? $("rag_redact_drop_matched_documents").checked : false,
    rag_redact_placeholder: $("rag_redact_placeholder") ? $("rag_redact_placeholder").value.trim() : "",
    rag_redact_terms: $("rag_redact_terms") ? $("rag_redact_terms").value.trim() : "",
    rag_redact_mappings: $("rag_redact_mappings") ? $("rag_redact_mappings").value.trim() : ""
  };
}

function selectedValues(id) {
  const element = $(id);
  if (!element) return [];
  if (element.multiple) {
    return Array.from(element.selectedOptions).map(option => option.value).filter(Boolean);
  }
  const value = String(element.value || "").trim();
  return value ? [value] : [];
}

function setSelectedValues(id, values) {
  const element = $(id);
  if (!element) return;
  const selected = new Set(
    Array.isArray(values)
      ? values.map(value => String(value))
      : String(values || "").split(",").map(value => value.trim()).filter(Boolean)
  );
  for (const option of Array.from(element.options || [])) {
    option.selected = selected.has(option.value);
  }
}

function vectorStorePayload() {
  const storeType = $("rag_vector_store_type") ? $("rag_vector_store_type").value : "local_jsonl";
  const location = $("rag_vector_store_url") ? $("rag_vector_store_url").value.trim() : "";
  return {
    ...ragPathPayload(),
    store_type: storeType,
    url: location,
    path: storeType === "qdrant_local" ? location : "",
    collection: $("rag_vector_store_collection") ? $("rag_vector_store_collection").value.trim() : ""
  };
}

function syncVectorStoreInputs() {
  const typeElement = $("rag_vector_store_type");
  const urlElement = $("rag_vector_store_url");
  const collectionElement = $("rag_vector_store_collection");
  const isJsonl = !typeElement || typeElement.value === "local_jsonl";
  if (urlElement) urlElement.disabled = isJsonl;
  if (collectionElement) collectionElement.disabled = isJsonl;
}

function syncRagRedactionInputs() {
  const enabled = !!($("rag_redaction_enabled") && $("rag_redaction_enabled").checked);
  for (const id of ["rag_redact_drop_matched_documents", "rag_redact_placeholder", "rag_redact_terms", "rag_redact_mappings"]) {
    const element = $(id);
    if (element) element.disabled = !enabled;
  }
}

function validateRagRedactionPayload(payload) {
  if (!payload || !payload.rag_redaction_enabled) return true;
  if (String(payload.rag_redact_terms || "").trim() || String(payload.rag_redact_mappings || "").trim()) {
    return true;
  }
  showToast(tr("rag_redaction_rules_required"));
  return false;
}

function pathQuery() {
  const query = new URLSearchParams(pathPayload());
  return query.toString();
}

function graphQuery() {
  const query = new URLSearchParams(graphPathPayload());
  return query.toString();
}

function ragQuery() {
  const query = new URLSearchParams(ragPathPayload());
  return query.toString();
}

async function refreshAnalysisStatus() {
  const query = pathQuery();
  const response = await fetch("/api/analysis/status" + (query ? "?" + query : ""));
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.error || tr("status_load_failed"));
    return null;
  }
  renderAnalysis(payload);
  return payload;
}

async function toggleAnalysis() {
  if (analysisActionBusy) return;
  analysisActionBusy = true;
  updateAnalysisButtons(lastAnalysisPayload || {});
  try {
    const payload = await refreshAnalysisStatus();
    if (!payload) return;
    if (payload.running) await stopAnalysis();
    else await startAnalysis(payload);
  } finally {
    analysisActionBusy = false;
    updateAnalysisButtons(lastAnalysisPayload || {});
  }
}

async function startAnalysis(currentPayload = null) {
  saveRunFormState();
  if (currentUploadWorkspace?.upload_id && !currentUploadWorkspace.complete) {
    return showToast(tr("upload_incomplete"));
  }
  const requestPayload = runPayload();
  if (!requestPayload.source_dir && !requestPayload.upload_id) {
    return showToast(tr("source_or_upload_required"));
  }
  if (!requestPayload.output_root) return showToast(tr("output_required"));
  requestPayload.preempt_relationships = true;
  const preemptRelationships = shouldPreemptRelationshipsForAnalysis(currentPayload);
  if (preemptRelationships) {
    showToast(tr("analysis_preempting_relationships"));
    const stopResult = await requestStopRelationships(requestPayload, {showToastMessage: false, refresh: false});
    if (!stopResult.ok || (stopResult.payload && stopResult.payload.running)) {
      loadAnalysis();
      return showToast((stopResult.payload && stopResult.payload.error) || tr("relationship_stop_failed"));
    }
    if (currentPayload) {
      currentPayload = {
        ...currentPayload,
        relationship_task: {
          ...((currentPayload && currentPayload.relationship_task) || {}),
          running: false,
          pid: null
        }
      };
    }
  }
  clearRelationshipLaunchPendingState();
  updateAnalysisButtons(currentPayload || lastAnalysisPayload || {});
  $("analysisStats").innerHTML = `<span class="pill">${escapeHtml(tr("testing_llm"))}</span>`;
  const endpointReady = await ensureEndpointReady(requestPayload, {
    role: "analysis",
    endpoint: requestPayload.llm_endpoint,
    model: requestPayload.llm_model
  });
  if (!endpointReady) {
    loadAnalysis();
    return;
  }
  const response = await fetch("/api/analysis/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(requestPayload)
  });
  const responsePayload = await response.json();
  if (!response.ok) {
    return showToast(responsePayload.error || tr("analysis_start_failed"));
  }
  showToast(tr("analysis_started"));
  loadAnalysis();
}

function shouldPreemptRelationshipsForAnalysis(payload = null) {
  const relationshipTask = effectiveRelationshipTaskForPayload(payload || lastAnalysisPayload);
  const graphTask = (graphMeta && graphMeta.task) || {};
  return !!relationshipTask.running || !!graphTask.running || !!relationshipLaunchPending;
}

function effectiveRelationshipTaskForPayload(payload = null) {
  const currentPayload = payload || {};
  const relationshipTask = currentPayload.relationship_task || {};
  if (relationshipStopPending) return relationshipStopPending;
  return relationshipTask.running ? relationshipTask : (pendingRelationshipTask() || relationshipTask);
}

function isInlineRelationshipTask(task) {
  return !!(task && task.running && task.inline);
}

function showRelationshipLaunchPending(payload) {
  relationshipLaunchPending = {
    useEmbeddings: !!(payload && payload.relationship_use_embeddings),
    startedAt: Date.now()
  };
  const task = pendingRelationshipTask();
  if (lastAnalysisPayload) renderAnalysis(lastAnalysisPayload);
  if ($("section-graph").classList.contains("active")) {
    renderGraphTaskStats(graphMeta || {task});
  } else {
    const graphTaskStats = $("graphTaskStats");
    if (graphTaskStats) graphTaskStats.innerHTML = `<span class="pill">${escapeHtml(relationshipTaskPillText(task))}</span>`;
    renderEmbeddingProgress(pendingEmbeddingProgress(), task);
    updateGraphButtons(graphMeta || {});
  }
}

function clearRelationshipLaunchPending(token = null) {
  if (token === null) relationshipLaunchToken += 1;
  else if (token !== relationshipLaunchToken) return;
  relationshipLaunchPending = null;
  if (lastAnalysisPayload) renderAnalysis(lastAnalysisPayload);
  else renderEmbeddingProgress({}, {});
  if ($("section-graph").classList.contains("active")) renderGraphTaskStats(graphMeta || {});
}

function pendingRelationshipTask() {
  if (!relationshipLaunchPending) return null;
  return {
    running: true,
    pending: true,
    kind: "mine",
    command: relationshipLaunchPending.useEmbeddings ? ["--use-embeddings"] : []
  };
}

function pendingEmbeddingProgress() {
  return {
    enabled: true,
    phase: "ready",
    percent: 0
  };
}

async function stopAnalysis() {
  updateAnalysisButtons({...lastAnalysisPayload, running: true});
  const response = await fetch("/api/analysis/stop", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(pathPayload())
  });
  const payload = await response.json();
  showToast(response.ok ? tr("stop_requested") : (payload.error || tr("stop_failed")));
  loadAnalysis();
}

async function stopRelationships() {
  const targetPayload = relationshipStopPayload();
  return requestStopRelationships(targetPayload);
}

function relationshipStopPayload() {
  const graphPaths = graphPathPayload();
  if ($("section-graph").classList.contains("active") && graphPaths.output_root) {
    return {...runPayload(), ...graphPaths};
  }
  const relationshipTask = effectiveRelationshipTaskForPayload(lastAnalysisPayload || {});
  if (relationshipTask && relationshipTask.output_root) {
    return {
      ...runPayload(),
      source_dir: relationshipTask.source_dir || (lastAnalysisPayload && lastAnalysisPayload.source_dir) || $("run_source_dir").value.trim(),
      output_root: relationshipTask.output_root
    };
  }
  if (lastAnalysisPayload && lastAnalysisPayload.output_root) {
    return {
      ...runPayload(),
      source_dir: lastAnalysisPayload.source_dir || $("run_source_dir").value.trim(),
      output_root: lastAnalysisPayload.output_root
    };
  }
  return runPayload();
}

async function requestStopRelationships(targetPayload, options = {}) {
  const showToastMessage = options.showToastMessage !== false;
  const refresh = options.refresh !== false;
  const pendingTask = effectiveRelationshipTaskForPayload(lastAnalysisPayload || {});
  if (pendingTask && pendingTask.running) relationshipStopPending = {...pendingTask, stopping: true};
  clearRelationshipLaunchPendingState();
  updateAnalysisButtons(lastAnalysisPayload || {});
  const response = await fetch("/api/relationships/stop", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(targetPayload || {})
  });
  const payload = await response.json();
  if (showToastMessage) {
    showToast(response.ok ? tr("relationship_stop_requested") : (payload.error || tr("relationship_stop_failed")));
  }
  if (refresh) {
    const refreshed = $("section-analysis").classList.contains("active") ? await loadAnalysis() : null;
    if (!(payload && payload.running)) {
      relationshipStopPending = null;
      if (refreshed) renderAnalysis(refreshed);
    }
    if ($("section-graph").classList.contains("active")) loadGraph();
  }
  return {ok: response.ok, payload};
}

function clearRelationshipLaunchPendingState() {
  relationshipLaunchToken += 1;
  relationshipLaunchPending = null;
}

function setActionButtonState(id, key, tone, disabled) {
  const button = $(id);
  if (!button) return;
  button.dataset.i18n = key;
  button.textContent = tr(key);
  button.classList.toggle("primary", tone === "primary");
  button.classList.toggle("danger", tone === "danger");
  button.disabled = !!disabled;
}

function updateAnalysisButtons(payload) {
  const currentPayload = payload || {};
  const effectiveRelationshipTask = effectiveRelationshipTaskForPayload(currentPayload);
  const relationshipActive = !!(effectiveRelationshipTask && effectiveRelationshipTask.running);
  const inlineRelationshipActive = relationshipActive && isInlineRelationshipTask(effectiveRelationshipTask);
  const analysisActive = !!currentPayload.running && !inlineRelationshipActive;
  setActionButtonState(
    "start_analysis_btn",
    analysisActive ? "stop_analysis" : "start_analysis",
    analysisActive ? "danger" : "primary",
    analysisActionBusy || inlineRelationshipActive
  );
  if ($("reset_analysis_btn")) {
    $("reset_analysis_btn").disabled = !!currentPayload.running || relationshipActive || analysisActionBusy || relationshipActionBusy;
  }
}

function clearReadingRows() {
  readingRowsLoadToken += 1;
  readingRowsLoadedKey = "";
  readingRowsLoadingKey = "";
  readingRowsLoading = false;
  allRows = [];
  filteredRows = [];
  currentRows = [];
  populateFacetOptions([]);
  renderStatsFromRows([], 0);
  renderPager();
  renderSortMarks();
  renderRows([]);
}

function renderReadingError(message) {
  const text = String(message || tr("rows_load_failed"));
  readingRowsLoading = false;
  readingRowsLoadedKey = "";
  readingRowsLoadingKey = "";
  allRows = [];
  filteredRows = [];
  currentRows = [];
  populateFacetOptions([]);
  $("stats").innerHTML = `<span class="pill status-failed">${escapeHtml(text)}</span>`;
  $("pagerTop").innerHTML = "";
  $("pagerBottom").innerHTML = "";
  renderSortMarks();
  $("rows").setAttribute("aria-busy", "false");
  $("rows").innerHTML = `<tr><td colspan="8" class="status-failed">${escapeHtml(text)}</td></tr>`;
}

function renderReadingLoading() {
  readingRowsLoading = true;
  currentRows = [];
  $("stats").innerHTML = `
    <span class="pill reading-loading-status" role="status">
      <span class="reading-loading-spinner" aria-hidden="true"></span>
      ${escapeHtml(tr("rows_loading"))}
    </span>`;
  $("pagerTop").innerHTML = "";
  $("pagerBottom").innerHTML = "";
  $("rows").setAttribute("aria-busy", "true");
  $("rows").setAttribute("aria-label", tr("rows_loading"));
  $("rows").innerHTML = Array.from({length: 6}, (_, index) => `
    <tr class="reading-loading-row" aria-hidden="true">
      <td><span class="reading-loading-spinner"></span></td>
      <td><span class="reading-loading-placeholder short"></span></td>
      <td><span class="reading-loading-placeholder short"></span></td>
      <td class="document-profile"><span class="reading-loading-placeholder medium"></span></td>
      <td class="name"><span class="reading-loading-placeholder long"></span></td>
      <td><span class="reading-loading-placeholder medium"></span></td>
      <td><span class="reading-loading-placeholder ${index % 2 ? "medium" : "long"}"></span></td>
      <td><span class="reading-loading-placeholder long"></span></td>
    </tr>`).join("");
}

function hasGraphPayload() {
  return !!(graphMeta && Object.keys(graphMeta).length);
}

function renderClearedGraphState() {
  const message = tr(graphClearMessageKey || "empty_graph");
  $("graphStats").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
  $("graphTaskStats").innerHTML = "";
  renderGraphProgress({});
  renderEmbeddingProgress({}, {});
  if ($("graphLog")) $("graphLog").textContent = "";
  $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
  $("graphClusterTitle").innerHTML = "";
  $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
  $("graphEdges").innerHTML = "";
  $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
  updateGraphButtons({});
}

function renderGraphError(message) {
  const text = String(message || tr("graph_load_failed"));
  graphMeta = {};
  graphClusters = [];
  filteredGraphClusters = [];
  graphSelectedClusterId = null;
  graphClusterData = null;
  graphSelectedDocPath = "";
  $("graphStats").innerHTML = `<span class="pill status-failed">${escapeHtml(text)}</span>`;
  $("graphTaskStats").innerHTML = "";
  renderGraphProgress({});
  renderEmbeddingProgress({}, {});
  if ($("graphLog")) $("graphLog").textContent = "";
  $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(text)}</div>`;
  $("graphClusterTitle").innerHTML = "";
  $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(text)}</div>`;
  $("graphEdges").innerHTML = "";
  $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(text)}</div>`;
  updateGraphButtons({});
}

function clearGraphState(messageKey = "empty_graph") {
  graphClearMessageKey = messageKey;
  graphMeta = {};
  graphClusters = [];
  filteredGraphClusters = [];
  graphSelectedClusterId = null;
  graphClusterData = null;
  graphSelectedDocPath = "";
  renderClearedGraphState();
}

function hasRagPayload() {
  return !!(ragMeta && Object.keys(ragMeta).length);
}

function clearRagState(messageKey = "rag_no_index") {
  ragMeta = {};
  ragSearchPayload = null;
  const message = tr(messageKey);
  $("ragTaskStats").innerHTML = `<span class="pill">${escapeHtml(message)}</span>`;
  $("ragBar").style.width = "0%";
  $("ragLog").textContent = "";
  $("ragResultStats").innerHTML = "";
  $("ragResults").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
  updateRagButtons({task: {running: false}});
}

async function resetAnalysis() {
  const paths = pathPayload();
  const sourceDir = paths.source_dir;
  const outputRoot = paths.output_root;
  if (!sourceDir || !outputRoot) return showToast(tr("need_source_output"));
  if (!window.confirm(trf("reset_confirm", {output: outputRoot}))) return;
  const response = await fetch("/api/analysis/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({source_dir: sourceDir, output_root: outputRoot})
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("reset_failed"));
  clearReadingRows();
  clearGraphState("output_reset");
  showToast(tr("output_reset"));
  loadAnalysis();
}

async function resetRelationships() {
  const sourceDir = $("run_source_dir").value.trim();
  const outputRoot = $("run_output_root").value.trim();
  if (!sourceDir || !outputRoot) return showToast(tr("need_source_output"));
  const payload = await refreshAnalysisStatus();
  if (!payload) return;
  const relationshipTask = effectiveRelationshipTaskForPayload(payload);
  const relationshipActive = !!(relationshipTask && relationshipTask.running) || !!relationshipLaunchPending;
  if (payload.running || relationshipActive) {
    updateAnalysisButtons(payload);
    return showToast(relationshipActive ? tr("reset_relationships_blocked_relationships") : tr("reset_relationships_blocked_analysis"));
  }
  if (!window.confirm(trf("reset_relationships_confirm", {output: outputRoot}))) return;
  const response = await fetch("/api/relationships/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({source_dir: sourceDir, output_root: outputRoot})
  });
  const responsePayload = await response.json();
  if (!response.ok) return showToast(responsePayload.error || tr("relationship_reset_failed"));
  clearGraphState("relationships_reset");
  showToast(tr("relationships_reset"));
  loadAnalysis();
  if ($("section-graph").classList.contains("active")) loadGraph();
}

async function resetGraph() {
  const paths = graphPathPayload();
  const outputRoot = paths.output_root;
  if (!outputRoot) return showToast(tr("graph_need_paths"));
  const payload = await loadGraph();
  if (!payload) return;
  const task = payload.task || {};
  if (task.running || relationshipLaunchPending) {
    updateGraphButtons(payload);
    return showToast(tr("reset_relationships_blocked_relationships"));
  }
  if (!window.confirm(trf("reset_relationships_confirm", {output: outputRoot}))) return;
  const response = await fetch("/api/relationships/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(paths)
  });
  const responsePayload = await response.json();
  if (!response.ok) return showToast(responsePayload.error || tr("relationship_reset_failed"));
  clearGraphState("relationships_reset");
  showToast(tr("relationships_reset"));
  await loadGraph();
  loadAnalysis();
}

async function loadAnalysis() {
  return refreshAnalysisStatus();
}

function renderAnalysis(payload) {
  lastAnalysisPayload = payload;
  syncReadingTarget(payload);
  const progress = payload.progress || {};
  const activity = payload.activity || {};
  const latest = activity.latest_activity || {};
  const lock = payload.run_lock || {};
  const summary = payload.run_summary || {};
  const unresolvedFailures = Number(summary.unresolved_failures ?? progress.failed ?? 0);
  const retryAttempted = Number(summary.retry_attempted || 0);
  const retrySucceeded = Number(summary.retry_succeeded || 0);
  const phaseText = localizedPhase(payload.phase);
  const rateReady = !!progress.rate_window_active && Number(progress.rate_window_completed || 0) > 0;
  const relationshipTask = payload.relationship_task || {};
  if (relationshipTask.running || relationshipTask.return_code !== null) relationshipLaunchPending = null;
  const effectiveRelationshipTask = effectiveRelationshipTaskForPayload(payload);
  const inlineRelationshipActive = isInlineRelationshipTask(effectiveRelationshipTask);
  const showAnalysisProgress = !inlineRelationshipActive;
  const parts = [
    phaseText,
    payload.plan_only ? tr("plan_only_pill") : "",
    inlineRelationshipActive ? "" : (payload.running ? tr("running_pill") : tr("not_running_pill")),
    relationshipTaskPillText(effectiveRelationshipTask),
    payload.pid ? "PID " + payload.pid : "",
    payload.effective_concurrency ? `${tr("concurrency_pill")} ${payload.effective_concurrency}` : "",
    showAnalysisProgress && progress.percent !== undefined ? `${tr("progress_pill")} ${progress.percent}%` : "",
    showAnalysisProgress && progress.completed !== undefined ? `${tr("completed_pill")} ${progress.completed}/${progress.total || 0}` : "",
    showAnalysisProgress && rateReady && progress.eta_human && progress.eta_human !== "unknown" ? `ETA ${progress.eta_human}` : (showAnalysisProgress && payload.running ? tr("eta_waiting_pill") : ""),
    showAnalysisProgress && rateReady && progress.files_per_minute !== undefined && Number(progress.files_per_minute) > 0 ? `${tr("speed_pill")} ${progress.files_per_minute}/min` : (showAnalysisProgress && payload.running ? tr("speed_waiting_pill") : ""),
    unresolvedFailures > 0 ? `${tr("unresolved_failures_pill")} ${unresolvedFailures}` : "",
    retryAttempted > 0 ? `${tr("retry_recovered_pill")} ${retrySucceeded}/${retryAttempted}` : "",
    lock.exists && !lock.active && lock.pid ? `${tr("stale_lock_pid_pill")} ${lock.pid}` : "",
    activityPillText(latest)
  ].filter(Boolean);
  $("analysisStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
  $("analysisBar").style.width = Math.max(0, Math.min(100, Number(progress.percent || 0))) + "%";
  $("analysisLog").textContent = payload.log_tail || "";
  const embeddingProgress = effectiveRelationshipTask.pending ? pendingEmbeddingProgress() : (payload.embedding_progress || {});
  const embeddingPhase = String((embeddingProgress && embeddingProgress.phase) || "").toLowerCase();
  const keepEmbeddingTask = !effectiveRelationshipTask.running && embeddingProgress && embeddingProgress.enabled && embeddingPhase !== "complete" && embeddingPhase !== "error"
    ? (lastEmbeddingTask || effectiveRelationshipTask || {})
    : effectiveRelationshipTask;
  if ($("section-graph").classList.contains("active")) {
    renderEmbeddingProgress(embeddingProgress, keepEmbeddingTask);
  }
  updateAnalysisButtons(payload);
}

function renderEmbeddingProgress(progress, task) {
  const command = task && Array.isArray(task.command) ? task.command : [];
  const embeddingTask = command.includes("--use-embeddings") || command.includes("--relationship-use-embeddings");
  const progressActive = !!(progress && progress.enabled && String(progress.phase || "").toLowerCase() !== "complete" && String(progress.phase || "").toLowerCase() !== "error");
  const activeEmbeddingTask = !!(task && (task.running || task.stopping) && embeddingTask);
  const visible = (activeEmbeddingTask || progressActive) && (!!(progress && progress.enabled) || !!(task && task.pending) || !progress || Object.keys(progress).length === 0);
  $("embeddingProgressWrap").style.display = visible ? "block" : "none";
  if (!visible) {
    $("embeddingProgressStats").innerHTML = "";
    $("embeddingProgressBar").style.width = "0%";
    return;
  }
  lastEmbeddingProgress = progress || {};
  lastEmbeddingTask = task || {};
  const percent = Math.max(0, Math.min(100, Number(progress.percent || 0)));
  const total = Number(progress.total || 0);
  const phase = localizedEmbeddingPhase(progress.phase || "ready");
  const itemsPerMinute = Number(progress.items_per_minute || 0);
  const etaHuman = String(progress.eta_human || "");
  const finishTime = formatEpochTime(progress.eta_finish_epoch);
  const speedReady = itemsPerMinute > 0;
  const progressPhase = String(progress.phase || "").toLowerCase();
  const progressComplete = progressPhase === "complete";
  const parts = [
    `${tr("embedding_progress_pill")} ${percent}%`,
    phase,
    total > 0 ? `${tr("completed_pill")} ${Number(progress.completed || 0)}/${total}` : "",
    speedReady ? `${tr("speed_pill")} ${itemsPerMinute}/min` : tr("embedding_speed_waiting_pill"),
    !progressComplete && speedReady && etaHuman && etaHuman !== "unknown" ? `ETA ${etaHuman}` : (!progressComplete ? tr("embedding_eta_waiting_pill") : ""),
    finishTime ? `${tr("eta_finish_pill")} ${finishTime}` : "",
    !progressComplete && progress.workers ? `${tr("concurrency_pill")} ${progress.workers}` : ""
  ].filter(Boolean);
  $("embeddingProgressStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
  $("embeddingProgressBar").style.width = percent + "%";
}

function formatEpochTime(epochSeconds) {
  const epoch = Number(epochSeconds || 0);
  if (!Number.isFinite(epoch) || epoch <= 0) return "";
  return new Date(epoch * 1000).toLocaleString(uiLanguage === "zh-CN" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function relationshipTaskPillText(task) {
  if (!task || !task.running) return "";
  return trf("graph_task_running", {task: graphTaskKindLabel(task.kind || "mine")});
}

function localizedEmbeddingPhase(phase) {
  const key = {
    loading_cache: "embedding_phase_loading_cache",
    embedding: "embedding_phase_embedding",
    complete: "embedding_phase_complete",
    ready: "embedding_phase_ready"
  }[phase];
  return key ? tr(key) : (phase || "");
}

function activityPillText(latest) {
  if (!latest || !latest.label) return "";
  const label = localizedActivityLabel(latest.label);
  const detail = localizedActivityDetail(latest.detail || "").trim();
  return detail ? `${label}: ${detail}` : label;
}

function localizedPhase(phase) {
  if (phase === "文档评分中") return "";
  const key = {
    "未启动": "phase_not_started",
    "关系挖掘中": "phase_relationship_mining",
    "续传准备中": "phase_resume_preparing",
    "续传跳过中": "phase_resume_skipping",
    "扫描准备中": "phase_scanning",
    "分析完成，仍有失败": "phase_completed_with_failures",
    "分析完成，关系已生成": "phase_completed_relationships",
    "分析完成，关系未生成": "phase_completed_no_relationships",
    "分析完成": "phase_completed",
    "已停止，可续传": "phase_stopped_resume"
  }[phase];
  return key ? tr(key) : (phase || "");
}

function localizedActivityLabel(label) {
  return label || "";
}

function localizedActivityDetail(detail) {
  return detail || "";
}

async function loadRows() {
  const loadKey = readingRowsCacheKey();
  const loadToken = ++readingRowsLoadToken;
  readingRowsLoadingKey = loadKey;
  syncReadingScopeControls();
  renderReadingLoading();
  try {
    const response = await fetch("/api/state?" + readingParams());
    const payload = await response.json();
    if (loadToken !== readingRowsLoadToken) return null;
    if (!response.ok) {
      const message = payload.error || tr("rows_load_failed");
      showToast(message);
      renderReadingError(message);
      return null;
    }
    allRows = payload.rows || [];
    populateFacetOptions(allRows);
    currentPage = 1;
    readingRowsLoading = false;
    readingRowsLoadedKey = loadKey;
    readingRowsLoadingKey = "";
    applyClientFilters();
    return payload;
  } catch (error) {
    if (loadToken !== readingRowsLoadToken) return null;
    const message = error?.message || tr("rows_load_failed");
    showToast(message);
    renderReadingError(message);
    return null;
  }
}

function syncReadingScopeControls() {
  if ($("reading_scope")) $("reading_scope").value = readingScope;
  const disabled = readingScope === "source";
  for (const id of ["min_quality", "categories", "topic_tags", "max_sensitivity_risk", "min_public_writing_suitability"]) {
    const element = $(id);
    if (element) element.disabled = disabled;
  }
}

function syncReadingTarget(payload) {
  if (!payload) return;
  let changed = false;
  const currentRunSource = $("run_source_dir").value.trim();
  const uploadOnlySource = !currentRunSource
    && currentUploadWorkspace?.complete
    && String(currentUploadWorkspace.source_dir || "") === String(payload.source_dir || "");
  if (payload.source_dir && !uploadOnlySource && $("run_source_dir").value !== payload.source_dir) {
    $("run_source_dir").value = payload.source_dir;
    changed = true;
  }
  if (payload.output_root && $("run_output_root").value !== payload.output_root) {
    $("run_output_root").value = payload.output_root;
    changed = true;
  }
  if (changed) {
    lastAppliedRunPathKey = runPathKey($("run_source_dir").value, $("run_output_root").value);
    syncReadingTargetFromRunOutput();
    saveRunFormState();
  } else if (!$("reading_output_root").value.trim()) {
    syncReadingTargetFromRunOutput();
  }
}

async function loadGraph(preserveSelection = true) {
  if (!graphPathPayload().output_root) {
    clearGraphState("graph_need_paths");
    return null;
  }
  const query = graphQuery();
  const response = await fetch("/api/relationships" + (query ? "?" + query : ""));
  const payload = await response.json();
  if (!response.ok) {
    const message = payload.error || tr("graph_load_failed");
    showToast(message);
    renderGraphError(message);
    return null;
  }
  graphMeta = payload;
  graphClusters = payload.clusters || [];
  renderGraphStats(payload);
  renderGraphTaskStats(payload);
  applyGraphFilters(preserveSelection);
  return payload;
}

async function loadRagStatus() {
  if (!ragPathPayload().output_root) {
    clearRagState("rag_need_output");
    return;
  }
  const query = ragQuery();
  const response = await fetch("/api/rag" + (query ? "?" + query : ""));
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("rag_load_failed"));
  ragMeta = payload;
  renderRagStatus(payload);
}

function renderRagStatus(payload) {
  const progress = payload.progress || {};
  const manifest = payload.manifest || {};
  const task = payload.task || {};
  const percent = Math.max(0, Math.min(100, Number(progress.percent || 0)));
  const parts = [];
  if (task.running) parts.push(tr("rag_task_running"));
  if (task.pid) parts.push(`PID ${task.pid}`);
  if (progress.phase) parts.push(localizedRagPhase(progress.phase));
  if (progress.total_documents !== undefined) parts.push(`${tr("rag_documents_pill")} ${Number(progress.indexed_documents || 0)}/${Number(progress.total_documents || 0)}`);
  if (progress.total_chunks !== undefined) parts.push(`${tr("rag_chunks_pill")} ${Number(progress.total_chunks || 0)}`);
  if (progress.embedded_chunks !== undefined) parts.push(`${tr("rag_vectors_pill")} ${Number(progress.embedded_chunks || 0)}`);
  if (Number(progress.failed_documents || manifest.failed_documents || 0) > 0) parts.push(`${tr("rag_failed_pill")} ${Number(progress.failed_documents || manifest.failed_documents || 0)}`);
  if (!payload.available && !task.running) parts.push(tr("rag_no_index"));
  $("ragTaskStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
  $("ragBar").style.width = percent + "%";
  $("ragLog").textContent = payload.log_tail || "";
  updateRagButtons(payload);
}

function updateRagButtons(payload) {
  const task = (payload || {}).task || {};
  const running = !!task.running;
  setActionButtonState(
    "start_rag_btn",
    running ? "stop_rag" : "build_rag",
    running ? "danger" : "primary",
    ragActionBusy
  );
}

function localizedRagPhase(phase) {
  const key = {
    loading_decisions: "rag_phase_loading_decisions",
    extracting_text: "rag_phase_extracting_text",
    chunking: "rag_phase_chunking",
    embedding: "rag_phase_embedding",
    complete: "rag_phase_complete",
    error: "rag_phase_error"
  }[phase];
  return key ? tr(key) : (phase || "");
}

async function startRagIndex() {
  if (!ragPathPayload().output_root) return showToast(tr("rag_need_output"));
  const requestPayload = ragPayload();
  if (!validateRagRedactionPayload(requestPayload)) return;
  updateRagButtons({task: {running: false}});
  $("ragTaskStats").innerHTML = `<span class="pill">${escapeHtml(tr("rag_task_running"))}</span>`;
  $("ragBar").style.width = "0%";
  const response = await fetch("/api/rag/build", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(requestPayload)
  });
  const responsePayload = await response.json();
  if (!response.ok) {
    updateRagButtons(ragMeta || {});
    return showToast(responsePayload.error || tr("rag_start_failed"));
  }
  showToast(tr("rag_started"));
  await loadRagStatus();
}

async function toggleRagIndex() {
  if (ragActionBusy) return;
  ragActionBusy = true;
  updateRagButtons(ragMeta || {});
  try {
    if (!ragPathPayload().output_root) return showToast(tr("rag_need_output"));
    await loadRagStatus();
    const task = (ragMeta || {}).task || {};
    if (task.running) await stopRagIndex();
    else await startRagIndex();
  } finally {
    ragActionBusy = false;
    updateRagButtons(ragMeta || {});
  }
}

async function stopRagIndex() {
  const response = await fetch("/api/rag/stop", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(ragPathPayload())
  });
  const payload = await response.json();
  showToast(response.ok ? tr("rag_stop_requested") : (payload.error || tr("rag_stop_failed")));
  await loadRagStatus();
}

async function searchRag() {
  const query = $("rag_query").value.trim();
  if (!query) return showToast(tr("rag_query_required"));
  const response = await fetch("/api/rag/search", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      ...ragPayload(),
      query,
      top_k: $("rag_top_k").value
    })
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("rag_search_failed"));
  ragSearchPayload = payload;
  renderRagResults(payload);
}

function renderRagResults(payload) {
  const results = payload.results || [];
  const mode = payload.mode === "vector" ? tr("rag_mode_vector") : tr("rag_mode_lexical");
  $("ragResultStats").innerHTML = [
    `<span class="pill">${escapeHtml(mode)}</span>`,
    `<span class="pill">${tr("rag_result_count")} ${results.length}</span>`,
    payload.vector_store ? `<span class="pill">${escapeHtml(String(payload.vector_store))}</span>` : "",
    ...(payload.warnings || []).map(item => `<span class="pill warning">${escapeHtml(String(item))}</span>`)
  ].join("");
  if (!results.length) {
    $("ragResults").innerHTML = `<div class="graph-empty">${escapeHtml(tr("rag_no_results"))}</div>`;
    return;
  }
  $("ragResults").innerHTML = results.map(item => `
    <div class="rag-result-item">
      <div class="rag-result-title">${escapeHtml(item.title || item.relative_path || item.source_path || item.chunk_id)}</div>
      <div class="rag-result-meta">${escapeHtml(item.relative_path || "")} · ${escapeHtml(item.category || "")} · score=${escapeHtml(item.score)} · q=${escapeHtml(item.quality)}</div>
      <div class="rag-result-excerpt">${escapeHtml(item.excerpt || "")}</div>
    </div>
  `).join("");
}

function renderGraphStats(payload) {
  const parts = [];
  if (payload.cluster_count !== undefined) parts.push(`${tr("cluster")} ${payload.cluster_count}`);
  if (payload.relations_exists) parts.push(tr("graph_relations_exists"));
  if (payload.clusters_exists) parts.push(tr("graph_clusters_exists"));
  if (payload.decisions_exists) parts.push(tr("graph_decisions_exists"));
  if (!payload.available) parts.push(tr("empty_graph"));
  $("graphStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
}

function graphTaskKindLabel(kind) {
  return {
    mine: tr("graph_task_mine"),
    export_graph: tr("graph_task_export_graph"),
    export_bundle: tr("graph_task_export_bundle")
  }[kind] || kind || "";
}

function localGraphTaskLabel(label, taskName = "") {
  const reverse = {
    "关系结果生成": "graph_task_mine",
    "图谱生成": "graph_task_mine",
    "知识图谱导出": "graph_task_export_graph",
    "Bundle 导出": "graph_task_export_bundle"
  };
  if (label && reverse[label]) return tr(reverse[label]);
  return graphTaskKindLabel(taskName || label);
}

function renderGraphTaskStats(payload) {
  const task = payload.task || {};
  const effectiveTask = pendingRelationshipTask() || task;
  const parts = [];
  if (effectiveTask.running) parts.push(trf("graph_task_running", {task: graphTaskKindLabel(effectiveTask.kind || "mine")}));
  if (effectiveTask.pid) parts.push(`PID ${effectiveTask.pid}`);
  if (!payload.decisions_exists) {
    parts.push(tr("graph_need_analysis_once"));
  }
  $("graphTaskStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
  renderGraphProgress(payload);
  const embeddingProgress = effectiveTask.pending ? pendingEmbeddingProgress() : (payload.embedding_progress || {});
  renderEmbeddingProgress(embeddingProgress, effectiveTask);
  if ($("graphLog")) $("graphLog").textContent = payload.log_tail || "";
  updateGraphButtons(payload);
}

function renderGraphProgress(payload) {
  const task = (payload && payload.task) || {};
  const progress = (payload && payload.progress) || {};
  const phase = String(progress.phase || "").toLowerCase();
  const visible = !!(task.running && (!task.kind || task.kind === "mine")) || !!(phase && phase !== "complete");
  const wrap = $("graphProgressWrap");
  if (!wrap) return;
  wrap.style.display = visible ? "block" : "none";
  const percent = Math.max(0, Math.min(100, Number(progress.percent || 0)));
  $("graphProgressBar").style.width = `${percent}%`;
  if (!visible) {
    $("graphProgressBar").style.width = "0%";
    $("graphProgressStats").innerHTML = "";
    return;
  }
  const parts = [
    `${tr("progress_pill")} ${percent}%`,
    localizedGraphPhase(progress.phase || (task.running ? "scoring_relationships" : "")),
    progress.total_records !== undefined ? `${tr("graph_records_pill")} ${Number(progress.total_records || 0)}` : "",
    progress.candidate_relations !== undefined ? `${tr("graph_candidates_pill")} ${Number(progress.candidate_relations || 0)}` : "",
    progress.embedded_records !== undefined ? `${tr("graph_embedded_pill")} ${Number(progress.embedded_records || 0)}` : "",
    progress.elapsed_seconds !== undefined ? `${tr("elapsed_pill")} ${formatDurationShort(Number(progress.elapsed_seconds || 0))}` : "",
    progress.message ? String(progress.message) : ""
  ].filter(Boolean);
  $("graphProgressStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
}

function localizedGraphPhase(phase) {
  const key = {
    loading_decisions: "graph_phase_loading_decisions",
    records_loaded: "graph_phase_records_loaded",
    preparing_embeddings: "graph_phase_preparing_embeddings",
    scoring_relationships: "graph_phase_scoring_relationships",
    writing_relations: "graph_phase_writing_relations",
    clustering: "graph_phase_clustering",
    complete: "graph_phase_complete",
    error: "graph_phase_error"
  }[String(phase || "").toLowerCase()];
  return key ? tr(key) : "";
}

function formatDurationShort(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds || 0)));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  if (hours) return `${hours}h${String(minutes).padStart(2, "0")}m`;
  if (minutes) return `${minutes}m${String(secs).padStart(2, "0")}s`;
  return `${secs}s`;
}

function updateGraphButtons(payload) {
  const currentPayload = payload || {};
  const task = currentPayload.task || {};
  const pendingTask = pendingRelationshipTask();
  const runningAny = !!task.running || !!pendingTask;
  const runningMine = !!(pendingTask || (task.running && (!task.kind || task.kind === "mine")));
  const canMine = !!currentPayload.decisions_exists;
  setActionButtonState(
    "graph_mine_btn",
    runningMine ? "stop_relationships" : "generate_relationships",
    runningMine ? "danger" : "primary",
    graphActionBusy || (!runningMine && (runningAny || !canMine))
  );
  if ($("reset_graph_btn")) {
    $("reset_graph_btn").disabled = runningAny || graphActionBusy;
  }
}

async function startGraphTask(taskName) {
  if (!graphPathPayload().output_root) {
    return showToast(tr("graph_need_paths"));
  }
  const requestPayload = taskName === "mine"
    ? graphRelationshipPayload()
    : {...runPayload(), ...graphPathPayload()};
  if (taskName === "mine") {
    saveRunFormState();
    if (!validateEmbeddingModelSelection(requestPayload)) return;
    const token = relationshipLaunchToken + 1;
    relationshipLaunchToken = token;
    showRelationshipLaunchPending(requestPayload);
    if (requestPayload.relationship_use_embeddings) {
      const endpointReady = await ensureEndpointReady(requestPayload, {
        role: "embedding",
        endpoint: requestPayload.embedding_endpoint,
        model: requestPayload.embedding_model
      });
      if (!endpointReady) {
        clearRelationshipLaunchPending(token);
        return;
      }
    }
    if (token !== relationshipLaunchToken) return;
  }
  const response = await fetch(`/api/relationships/${taskName.replace("_", "-")}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(requestPayload)
  });
  const responsePayload = await response.json();
  if (!response.ok) {
    if (taskName === "mine") clearRelationshipLaunchPending();
    return showToast(responsePayload.error || tr("graph_task_start_failed"));
  }
  if (taskName === "mine") relationshipLaunchPending = null;
  showToast(trf("graph_task_started", {task: localGraphTaskLabel(responsePayload.label, taskName)}));
  await loadGraph();
}

async function toggleGraphRelationships() {
  if (graphActionBusy) return;
  graphActionBusy = true;
  updateGraphButtons(graphMeta || {});
  try {
    if (!graphPathPayload().output_root) {
      return showToast(tr("graph_need_paths"));
    }
    const payload = await loadGraph();
    if (!payload) return;
    const task = payload.task || {};
    if (task.running && (!task.kind || task.kind === "mine")) {
      await stopRelationships();
      return;
    }
    if (task.running) return;
    await startGraphTask("mine");
  } finally {
    graphActionBusy = false;
    updateGraphButtons(graphMeta || {});
  }
}

function renderAnydocsStats() {
  if (!$("anydocsStats")) return;
  const bundlePath = anydocsBundlePath();
  const parts = [];
  parts.push(tr("bundle_min_quality") + ": " + anydocsBundleMinQuality());
  if (bundlePath) parts.push(`${tr("anydocs_bundle_path")}: ${bundlePath}`);
  parts.push(tr("anydocs_optional"));
  $("anydocsStats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
  renderAnydocsQualityStats();
}

function anydocsBundleMinQuality() {
  return normalizeQualityScore($("anydocs_bundle_min_quality")?.value || "0");
}

function normalizeQualityScore(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.min(100, Math.trunc(parsed)));
}

function qualityCountAtOrAbove(histogram, threshold) {
  return histogram
    .slice(normalizeQualityScore(threshold))
    .reduce((sum, count) => sum + Number(count || 0), 0);
}

function qualityPercent(count, total) {
  return total > 0 ? (count * 100 / total).toFixed(1) : "0.0";
}

function renderAnydocsQualityStats() {
  const statsElement = $("anydocs_bundle_quality_stats");
  const helpElement = $("anydocs_bundle_quality_help");
  if (!statsElement || !helpElement) return;
  if (!anydocsBundleQualityHistogram.length || anydocsBundleQualityTotal <= 0) {
    statsElement.textContent = tr("quality_stats_unavailable");
    helpElement.dataset.tip = tr("tip_bundle_min_quality");
    refreshHelpTooltip();
    return;
  }
  const threshold = anydocsBundleMinQuality();
  const currentCount = qualityCountAtOrAbove(anydocsBundleQualityHistogram, threshold);
  statsElement.textContent = trf("quality_current_stats", {
    value: threshold,
    count: currentCount.toLocaleString(),
    total: anydocsBundleQualityTotal.toLocaleString(),
    percent: qualityPercent(currentCount, anydocsBundleQualityTotal)
  });
  const bands = [0, 25, 50, 75, 90].map(value => {
    const count = qualityCountAtOrAbove(anydocsBundleQualityHistogram, value);
    return value + "+: " + count.toLocaleString() + " / "
      + anydocsBundleQualityTotal.toLocaleString() + " ("
      + qualityPercent(count, anydocsBundleQualityTotal) + "%)";
  });
  const categoryExclusion = anydocsBundleExcludedCategoryCount > 0
    || anydocsBundleExcludedCategories.length
    ? trf("quality_category_exclusions", {
      count: anydocsBundleExcludedCategoryCount.toLocaleString(),
      total: anydocsBundleSourceTotal.toLocaleString(),
      categories: anydocsBundleExcludedCategories.join(", ") || "-"
    })
    : "";
  const helpLines = [tr("tip_bundle_min_quality")];
  if (categoryExclusion) helpLines.push(categoryExclusion);
  helpLines.push("", tr("quality_distribution"), ...bands);
  helpElement.dataset.tip = helpLines.join("\n");
  refreshHelpTooltip();
}

async function loadAnydocsQualityStats() {
  const paths = anydocsPathPayload();
  if (!paths.output_root) {
    anydocsBundleQualityHistogram = [];
    anydocsBundleQualityTotal = 0;
    anydocsBundleSourceTotal = 0;
    anydocsBundleExcludedCategoryCount = 0;
    anydocsBundleExcludedCategories = [];
    renderAnydocsQualityStats();
    return;
  }
  const statsKey = paths.source_dir + "\u0000" + paths.output_root;
  if (statsKey === anydocsQualityStatsKey && anydocsBundleQualityHistogram.length) {
    renderAnydocsQualityStats();
    return;
  }
  if ($("anydocs_bundle_quality_stats")) {
    $("anydocs_bundle_quality_stats").textContent = tr("quality_stats_loading");
  }
  const params = new URLSearchParams(paths);
  try {
    const response = await fetch("/api/integrations/anydocs/quality-stats?" + params.toString());
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || tr("quality_stats_unavailable"));
    anydocsBundleQualityHistogram = Array.isArray(payload.histogram) ? payload.histogram : [];
    anydocsBundleQualityTotal = Number(payload.total || 0);
    anydocsBundleSourceTotal = Number(payload.source_total || anydocsBundleQualityTotal);
    anydocsBundleExcludedCategoryCount = Number(payload.excluded_category_count || 0);
    anydocsBundleExcludedCategories = Array.isArray(payload.excluded_categories)
      ? payload.excluded_categories
      : [];
    anydocsQualityStatsKey = statsKey;
  } catch (error) {
    anydocsBundleQualityHistogram = [];
    anydocsBundleQualityTotal = 0;
    anydocsBundleSourceTotal = 0;
    anydocsBundleExcludedCategoryCount = 0;
    anydocsBundleExcludedCategories = [];
    anydocsQualityStatsKey = "";
  }
  renderAnydocsQualityStats();
}

function renderAnydocsOpenStatus() {
  const panel = $("anydocs_open_status_panel");
  const status = $("anydocs_open_status");
  if (!panel || !status) return;
  if (!anydocsUnavailableServiceUrl) {
    panel.hidden = true;
    status.textContent = "";
    return;
  }
  status.textContent = trf(
    anydocsGithubOpened
      ? "anydocs_service_unavailable"
      : "anydocs_service_unavailable_github",
    {url: anydocsUnavailableServiceUrl}
  );
  panel.hidden = false;
}

function clearAnydocsOpenStatus() {
  anydocsUnavailableServiceUrl = "";
  anydocsGithubOpened = false;
  renderAnydocsOpenStatus();
}

async function exportAndOpenAnyDocs() {
  const paths = anydocsPathPayload();
  if (!paths.output_root) return showToast(tr("graph_need_paths"));
  clearAnydocsOpenStatus();
  saveAnydocsTargetState();
  const response = await fetch("/api/integrations/anydocs/open", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      ...paths,
      anydocs_url: $("anydocs_url").value.trim() || DEFAULT_ANYDOCS_URL,
      export_bundle: true,
      bundle_min_quality: anydocsBundleMinQuality()
    })
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("anydocs_open_failed"));
  if ($("anydocs_bundle_path")) $("anydocs_bundle_path").value = payload.bundle_path || anydocsBundlePath();
  if (payload.service_available === false || payload.opened === false) {
    anydocsUnavailableServiceUrl = String(payload.service_url || $("anydocs_url").value || DEFAULT_ANYDOCS_URL);
    anydocsGithubOpened = payload.github_opened === true;
    renderAnydocsOpenStatus();
    showToast(tr(anydocsGithubOpened ? "anydocs_github_opened" : "anydocs_github_open_failed"));
    renderAnydocsStats();
    return;
  }
  showToast(tr("anydocs_opened"));
  renderAnydocsStats();
}

function renderGraphEmptyState() {
  const message = graphEmptyMessage(graphMeta);
  $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(message)}</div>`;
  $("graphEdges").innerHTML = "";
  $("graphClusterTitle").innerHTML = "";
  $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
}

function graphMatchesFilters(cluster) {
  const minSize = Number($("graph_min_size").value || 2);
  if (Number(cluster.size || 0) < minSize) return false;
  const q = $("graph_q").value.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    ...(cluster.categories || []),
    ...(cluster.preview_paths || [])
  ].join(" ").toLowerCase();
  return haystack.includes(q);
}

function applyGraphFilters(preserveSelection = true) {
  filteredGraphClusters = graphClusters.filter(graphMatchesFilters);
  renderGraphClusterList();
  if (!filteredGraphClusters.length) {
    graphSelectedClusterId = null;
    graphClusterData = null;
    graphSelectedDocPath = "";
    if (graphClusters.length) {
      $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_match"))}</div>`;
      $("graphEdges").innerHTML = "";
      $("graphClusterTitle").innerHTML = "";
      $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
    } else {
      renderGraphEmptyState();
    }
    return;
  }
  const hasSelection = preserveSelection && filteredGraphClusters.some(item => item.cluster_id === graphSelectedClusterId);
  if (hasSelection) {
    renderGraphClusterList();
    if (graphClusterData && graphClusterData.cluster_id === graphSelectedClusterId) {
      renderGraphCluster();
      return;
    }
  }
  loadGraphCluster(filteredGraphClusters[0].cluster_id, false);
}

async function loadGraphCluster(clusterId, preserveDocSelection = true) {
  graphSelectedClusterId = clusterId;
  renderGraphClusterList();
  const query = new URLSearchParams(graphPathPayload());
  query.set("cluster", String(clusterId));
  const response = await fetch("/api/relationships?" + query.toString());
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("graph_cluster_load_failed"));
  graphClusterData = payload.selected_cluster;
  if (!graphClusterData) {
    graphSelectedDocPath = "";
  } else if (!preserveDocSelection || !graphClusterData.files.some(item => item.relative_path === graphSelectedDocPath)) {
    graphSelectedDocPath = graphClusterData.files[0] ? graphClusterData.files[0].relative_path : "";
  }
  renderGraphCluster();
}

function renderGraphClusterList() {
  if (!filteredGraphClusters.length) {
    $("graphClusters").innerHTML = `<div class="graph-empty">${escapeHtml(graphEmptyMessage(graphMeta))}</div>`;
    return;
  }
  $("graphClusters").innerHTML = filteredGraphClusters.map(cluster => `
    <button class="graph-cluster-item ${cluster.cluster_id === graphSelectedClusterId ? "active" : ""}" onclick="loadGraphCluster(${cluster.cluster_id}, false)">
      <div class="graph-cluster-title">${tr("cluster")} ${cluster.cluster_id + 1} · ${cluster.size} ${tr("documents_unit")}</div>
      <div class="graph-cluster-preview">${escapeHtml((cluster.categories || []).join(", ") || tr("uncategorized"))}</div>
      <div class="graph-cluster-preview">${escapeHtml((cluster.preview_paths || []).join(" / ") || tr("no_preview_path"))}</div>
    </button>
  `).join("");
}

function renderGraphCluster() {
  if (!graphClusterData) {
    $("graphClusterTitle").innerHTML = "";
    $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(graphEmptyMessage(graphMeta))}</div>`;
    $("graphEdges").innerHTML = "";
    $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(graphDetailEmptyMessage(graphMeta))}</div>`;
    return;
  }
  const categories = (graphClusterData.categories || []).join(", ") || tr("uncategorized");
  $("graphClusterTitle").innerHTML = [
    `<span class="pill">${tr("cluster")} ${graphClusterData.cluster_id + 1}</span>`,
    `<span class="pill">${graphClusterData.size} ${tr("documents_unit")}</span>`,
    `<span class="pill">${graphClusterData.edge_count} ${tr("edges_unit")}</span>`,
    `<span class="pill">${escapeHtml(categories)}</span>`
  ].join("");
  renderGraphCanvas();
  renderGraphEdges();
  renderGraphDetail();
}

function graphDisplayName(relativePath) {
  const value = String(relativePath || "");
  const parts = value.split(/[\\\\/]/);
  return parts[parts.length - 1] || value;
}

function graphShortLabel(relativePath, maxLength = 18) {
  const name = graphDisplayName(relativePath).replace(/\.[^.]+$/, "");
  return name.length <= maxLength ? name : name.slice(0, maxLength - 1) + "…";
}

function graphColorForCategory(category) {
  const value = String(category || "Unknown");
  let hash = 0;
  for (const ch of value) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${hash}, 68%, 55%)`;
}

function graphNodePositionMap(files, selectedPath) {
  const width = 760;
  const height = 460;
  const centerX = width / 2;
  const centerY = height / 2;
  const positions = {};
  const ordered = files.map(item => item.relative_path);
  const anchor = selectedPath && ordered.includes(selectedPath) ? selectedPath : ordered[0];
  if (!anchor) return {width, height, positions};
  positions[anchor] = {x: centerX, y: centerY};
  const others = ordered.filter(path => path !== anchor);
  const radius = Math.min(width, height) * 0.34;
  others.forEach((path, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(others.length, 1);
    positions[path] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
  return {width, height, positions};
}

function renderGraphCanvas() {
  const files = graphClusterData.files || [];
  if (!files.length) {
    $("graphCanvas").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_docs"))}</div>`;
    return;
  }
  const selectedPath = graphSelectedDocPath || files[0].relative_path;
  const layout = graphNodePositionMap(files, selectedPath);
  const edges = (graphClusterData.edges || []).map(edge => {
    const left = layout.positions[edge.left_path];
    const right = layout.positions[edge.right_path];
    if (!left || !right) return "";
    const active = edge.left_path === selectedPath || edge.right_path === selectedPath;
    const stroke = active ? "#2563eb" : "#94a3b8";
    const opacity = active ? 0.9 : 0.45;
    const width = Math.max(1.5, Number(edge.relation_score || 0) * 3);
    const title = `${edge.left_path} ↔ ${edge.right_path} | score=${edge.relation_score} | ${(edge.signals || []).join(", ")}`;
    return `<line x1="${left.x}" y1="${left.y}" x2="${right.x}" y2="${right.y}" stroke="${stroke}" stroke-width="${width}" opacity="${opacity}"><title>${escapeHtml(title)}</title></line>`;
  }).join("");
  const nodes = files.map(file => {
    const point = layout.positions[file.relative_path];
    const selected = file.relative_path === selectedPath;
    const radius = selected ? 22 : 18;
    const fill = graphColorForCategory(file.category);
    const stroke = selected ? "#172033" : "#ffffff";
    const title = `${file.relative_path} | ${file.category} | q=${file.quality} | ${labelStatus(file.status)}`;
    return `
      <g onclick='selectGraphDoc(${JSON.stringify(file.relative_path)})' style="cursor:pointer">
        <circle cx="${point.x}" cy="${point.y}" r="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="${selected ? 3 : 2}"><title>${escapeHtml(title)}</title></circle>
        <text x="${point.x}" y="${point.y + radius + 16}" text-anchor="middle" font-size="11" fill="#172033">${escapeHtml(graphShortLabel(file.relative_path))}</text>
      </g>
    `;
  }).join("");
  $("graphCanvas").innerHTML = `<svg class="graph-svg" viewBox="0 0 ${layout.width} ${layout.height}" preserveAspectRatio="xMidYMid meet">${edges}${nodes}</svg>`;
}

function selectGraphDoc(relativePath) {
  graphSelectedDocPath = relativePath;
  renderGraphCanvas();
  renderGraphEdges();
  renderGraphDetail();
}

function renderGraphEdges() {
  if (!graphClusterData) {
    $("graphEdges").innerHTML = "";
    return;
  }
  const selectedPath = graphSelectedDocPath;
  let edges = graphClusterData.edges || [];
  if (selectedPath) {
    edges = edges.filter(edge => edge.left_path === selectedPath || edge.right_path === selectedPath);
  }
  edges = [...edges].sort((a, b) => Number(b.relation_score || 0) - Number(a.relation_score || 0)).slice(0, 18);
  if (!edges.length) {
    $("graphEdges").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_no_edges"))}</div>`;
    return;
  }
  $("graphEdges").innerHTML = edges.map(edge => {
    const title = `${graphDisplayName(edge.left_path)} ↔ ${graphDisplayName(edge.right_path)}`;
    const signals = (edge.signals || []).join(", ") || tr("no_explicit_signal");
    return `
      <div class="graph-edge-item">
        <div class="graph-cluster-title">${escapeHtml(title)}</div>
        <div class="muted">score ${edge.relation_score} · ${escapeHtml(signals)}</div>
      </div>
    `;
  }).join("");
}

function graphNeighborPath(edge, relativePath) {
  return edge.left_path === relativePath ? edge.right_path : edge.left_path;
}

function graphEmptyMessage(payload) {
  const task = (payload && payload.task) || {};
  if (task.running) return trf("graph_task_running_refresh", {task: graphTaskKindLabel(task.kind)});
  if (payload && !payload.decisions_exists) return tr("graph_need_analysis_before_graph");
  if (payload && payload.decisions_exists && !payload.relations_exists) return tr("graph_no_relationships_generate");
  return tr("empty_graph");
}

function graphDetailEmptyMessage(payload) {
  const task = (payload && payload.task) || {};
  if (task.running) return tr("graph_task_running_detail");
  if (payload && payload.decisions_exists && !payload.relations_exists) return tr("graph_generate_then_detail");
  return tr("graph_select_cluster");
}

async function graphMarkDoc(relativePath, status) {
  await markDoc(relativePath, status);
  if (graphSelectedClusterId !== null) {
    await loadGraphCluster(graphSelectedClusterId, true);
  }
}

function renderGraphDetail() {
  if (!graphClusterData || !graphClusterData.files || !graphClusterData.files.length) {
    $("graphDocDetail").innerHTML = `<div class="graph-empty">${escapeHtml(tr("graph_select_cluster"))}</div>`;
    return;
  }
  const selected = graphClusterData.files.find(item => item.relative_path === graphSelectedDocPath) || graphClusterData.files[0];
  graphSelectedDocPath = selected.relative_path;
  const relatedEdges = (graphClusterData.edges || [])
    .filter(edge => edge.left_path === selected.relative_path || edge.right_path === selected.relative_path)
    .sort((a, b) => Number(b.relation_score || 0) - Number(a.relation_score || 0));
  $("graphDocDetail").innerHTML = `
    <div class="graph-detail-card">
      <div class="graph-cluster-title">${escapeHtml(graphDisplayName(selected.relative_path))}</div>
      <div class="muted">${escapeHtml(selected.relative_path)}</div>
      <div class="stats">
        <span class="pill">${escapeHtml(labelStatus(selected.status))}</span>
        <span class="pill">q ${selected.quality}</span>
        <span class="pill">${escapeHtml(selected.category)}</span>
        <span class="pill">${escapeHtml(selected.document_kind || "Unknown")}</span>
      </div>
      <div class="stats">
        <span class="pill">${tr("sensitive")} ${selected.sensitivity_risk}</span>
        <span class="pill">${tr("public_label")} ${selected.public_writing_suitability}</span>
      </div>
      <p class="muted">${escapeHtml(selected.summary || tr("no_summary"))}</p>
      <div class="graph-actions">
        <button ${capabilities.open_file === false ? "disabled" : ""} onclick='openDoc(${JSON.stringify(selected.relative_path)})'>${tr("open")}</button>
        <button ${capabilities.reveal_file === false ? "disabled" : ""} onclick='revealDoc(${JSON.stringify(selected.relative_path)})'>${tr("reveal")}</button>
        <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "reading")'>${tr("mark_reading")}</button>
        <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "read")'>${tr("mark_read")}</button>
        <button onclick='graphMarkDoc(${JSON.stringify(selected.relative_path)}, "deferred")'>${tr("mark_deferred")}</button>
      </div>
    </div>
    <div class="graph-detail-card">
      <div class="graph-cluster-title">${tr("related_documents")}</div>
      ${relatedEdges.length ? relatedEdges.map(edge => {
        const neighbor = graphNeighborPath(edge, selected.relative_path);
        return `
          <div style="display:grid; gap:4px; margin-top:8px;">
            <button class="graph-cluster-item" style="padding:8px;" onclick='selectGraphDoc(${JSON.stringify(neighbor)})'>
              <div class="graph-cluster-title">${escapeHtml(graphDisplayName(neighbor))}</div>
              <div class="muted">score ${edge.relation_score} · ${escapeHtml((edge.signals || []).join(", ") || tr("no_explicit_signal"))}</div>
            </button>
          </div>
        `;
      }).join("") : `<div class="muted" style="margin-top:8px;">${escapeHtml(tr("no_related_edges"))}</div>`}
    </div>
  `;
}

function applyClientFilters() {
  if (readingRowsLoading) return;
  filteredRows = sortRowsClient(allRows.filter(rowMatchesFilters), sortKey);
  const pageCount = pageCountFor(filteredRows.length);
  currentPage = Math.min(Math.max(currentPage, 1), pageCount);
  renderStatsFromRows(filteredRows, allRows.length);
  renderPager();
  renderSortMarks();
  renderPageRows();
}

function renderPageRows() {
  const start = (currentPage - 1) * pageSize;
  currentRows = filteredRows.slice(start, start + pageSize);
  renderRows(currentRows);
}

function renderStatsFromRows(rows, totalCount) {
  const counts = countStatus(rows);
  const parts = [`${tr("match_prefix")} ${rows.length} / ${tr("all_prefix")} ${totalCount}`];
  for (const key of ["failed","unread","reading","read","reread_needed","skipped","deferred"]) {
    if (counts[key]) parts.push(`${labelStatus(key)} ${counts[key]}`);
  }
  $("stats").innerHTML = parts.map(x => `<span class="pill">${escapeHtml(x)}</span>`).join("");
}

function renderPager() {
  const pageCount = pageCountFor(filteredRows.length);
  const start = filteredRows.length ? ((currentPage - 1) * pageSize + 1) : 0;
  const end = Math.min(currentPage * pageSize, filteredRows.length);
  const html = `
    <span class="muted">${start}-${end} / ${filteredRows.length}</span>
    <button onclick="setPage(1)" ${currentPage <= 1 ? "disabled" : ""}>${tr("first_page")}</button>
    <button onclick="setPage(${currentPage - 1})" ${currentPage <= 1 ? "disabled" : ""}>${tr("previous_page")}</button>
    <span>${tr("page_label")} <input value="${currentPage}" onchange="setPage(Number(this.value))" /> / ${pageCount} ${tr("page_suffix")}</span>
    <button onclick="setPage(${currentPage + 1})" ${currentPage >= pageCount ? "disabled" : ""}>${tr("next_page")}</button>
    <button onclick="setPage(${pageCount})" ${currentPage >= pageCount ? "disabled" : ""}>${tr("last_page")}</button>
    <label style="display:inline-flex; align-items:center; gap:4px;">${tr("page_size_label")} <input value="${pageSize}" min="1" onchange="setPageSize(Number(this.value))" /></label>`;
  $("pagerTop").innerHTML = html;
  $("pagerBottom").innerHTML = html;
}

function rowMatchesFilters(row) {
  const status = $("status").value;
  if (status && row.status !== status) return false;
  const q = $("q").value.trim().toLowerCase();
  if (readingScope === "source" || row.source_only || row.status === "failed") {
    return !q || rowMatchesSearch(row, q);
  }
  const minQuality = Number($("min_quality").value || 0);
  if (Number(row.quality || 0) < minQuality) return false;
  const maxSensitivity = $("max_sensitivity_risk").value.trim();
  if (maxSensitivity && Number(row.sensitivity_risk || 0) > Number(maxSensitivity)) return false;
  const minPublic = $("min_public_writing_suitability").value.trim();
  if (minPublic && Number(row.public_writing_suitability || 0) < Number(minPublic)) return false;

  const selectedCategories = selectedValues("categories");
  if (selectedCategories.length && selectedCategories.length < $("categories").options.length && !selectedCategories.includes(row.category)) return false;

  const selectedTags = selectedValues("topic_tags");
  if (selectedTags.length && selectedTags.length < $("topic_tags").options.length) {
    const rowTags = row.topic_tags || [];
    if (!selectedTags.some(tag => rowTags.includes(tag))) return false;
  }

  if (q && !rowMatchesSearch(row, q)) return false;
  return true;
}

function rowMatchesSearch(row, q) {
  const haystack = [
    row.relative_path || "",
    row.source_path || "",
    row.category || "",
    row.document_kind || "",
    row.summary || "",
    row.reason || "",
    row.failure_stage || "",
    row.failure_reason || "",
    row.failure_error || "",
    (row.topic_tags || []).join(" "),
    row.note || ""
  ].join(" ").toLowerCase();
  return haystack.includes(q);
}

function exportFilteredRows(format) {
  const rows = filteredRows || [];
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const extension = format === "jsonl" ? "jsonl" : "csv";
  const filename = `doctriage-${readingScope}-${timestamp}.${extension}`;
  const content = format === "jsonl" ? rowsToJsonl(rows) : rowsToCsv(rows);
  const mime = format === "jsonl" ? "application/x-ndjson;charset=utf-8" : "text/csv;charset=utf-8";
  downloadText(filename, content, mime);
  showToast(`${tr("exported_rows")} ${rows.length}`);
}

function exportRow(row) {
  return {
    relative_path: row.relative_path || "",
    source_path: row.source_path || "",
    status: row.status || "",
    quality: row.quality ?? "",
    category: row.category || "",
    document_kind: row.document_kind || "",
    topic_tags: (row.topic_tags || []).join(", "),
    sensitivity_risk: row.sensitivity_risk ?? "",
    public_writing_suitability: row.public_writing_suitability ?? "",
    source_mtime: row.source_mtime || "",
    source_size_bytes: row.source_size_bytes ?? "",
    summary: row.summary || "",
    reason: row.reason || "",
    knowledge_density: row.knowledge_density ?? "",
    implementation_specificity: row.implementation_specificity ?? "",
    logical_structure: row.logical_structure ?? "",
    evidence_richness: row.evidence_richness ?? "",
    actionability: row.actionability ?? "",
    strategic_value: row.strategic_value ?? "",
    freshness: row.freshness ?? "",
    uniqueness: row.uniqueness ?? "",
    note: row.note || "",
    attempts: row.attempts ?? "",
    failure_stage: row.failure_stage || "",
    failure_reason: row.failure_reason || "",
    failure_error: row.failure_error || ""
  };
}

function rowsToJsonl(rows) {
  return rows.map(row => JSON.stringify(exportRow(row))).join("\n") + (rows.length ? "\n" : "");
}

function rowsToCsv(rows) {
  const headers = [
    "relative_path",
    "source_path",
    "status",
    "quality",
    "category",
    "document_kind",
    "topic_tags",
    "sensitivity_risk",
    "public_writing_suitability",
    "source_mtime",
    "source_size_bytes",
    "summary",
    "reason",
    "knowledge_density",
    "implementation_specificity",
    "logical_structure",
    "evidence_richness",
    "actionability",
    "strategic_value",
    "freshness",
    "uniqueness",
    "note",
    "attempts",
    "failure_stage",
    "failure_reason",
    "failure_error"
  ];
  const lines = [headers.join(",")];
  for (const row of rows) {
    const item = exportRow(row);
    lines.push(headers.map(header => csvCell(item[header])).join(","));
  }
  return lines.join("\n") + "\n";
}

function csvCell(value) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadText(filename, content, mime) {
  const blob = new Blob([content], {type: mime});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function populateFacetOptions(rows) {
  const categories = Array.from(new Set(rows.map(row => row.category).filter(Boolean))).sort();
  const tags = Array.from(new Set(rows.flatMap(row => row.topic_tags || []).filter(Boolean))).sort();
  populateMultiSelect("categories", categories);
  populateMultiSelect("topic_tags", tags);
}

function populateMultiSelect(id, values) {
  const select = $(id);
  const selected = new Set(selectedValues(id));
  select.innerHTML = values.map(value =>
    `<option value="${escapeAttrValue(value)}" ${selected.has(value) ? "selected" : ""}>${escapeHtml(value)}</option>`
  ).join("");
}

function selectMulti(id, checked) {
  Array.from($(id).options).forEach(option => option.selected = checked);
  handleMultiSelectionChanged(id);
}

function handleMultiSelectionChanged(id) {
  if (id === "rag_categories") {
    saveRagTargetState();
    return;
  }
  currentPage = 1;
  applyClientFilters();
}

function invertMulti(id) {
  Array.from($(id).options).forEach(option => option.selected = !option.selected);
  handleMultiSelectionChanged(id);
}

function countStatus(rows) {
  const counts = {};
  rows.forEach(row => counts[row.status] = (counts[row.status] || 0) + 1);
  return counts;
}

function setSort(field) {
  const next = {
    quality: sortKey === "quality_desc" ? "quality_asc" : "quality_desc",
    path: sortKey === "source_path_asc" || sortKey === "path_asc" ? "source_path_desc" : "source_path_asc",
    source_mtime: sortKey === "source_mtime_desc" ? "source_mtime_asc" : "source_mtime_desc",
    category: sortKey === "category_asc" ? "category_desc" : "category_asc",
    status: sortKey === "status_asc" ? "status_desc" : "status_asc",
    document_kind: sortKey === "kind_asc" ? "kind_desc" : "kind_asc",
    sensitivity: sortKey === "sensitivity_asc" ? "sensitivity_desc" : "sensitivity_asc",
    public: sortKey === "public_desc" ? "public_asc" : "public_desc"
  };
  sortKey = next[field] || defaultSortForScope(readingScope);
  localStorage.setItem(sortStorageKey(readingScope), sortKey);
  currentPage = 1;
  applyClientFilters();
}

function sortRowsClient(rows, key) {
  const sorted = [...rows];
  const text = value => String(value || "").toLowerCase();
  const num = value => Number(value || 0);
  const sourcePath = row => text(row.source_path || row.relative_path);
  const sourceMtime = row => Number(row.source_mtime_epoch || 0);
  const comparators = {
    quality_desc: (a, b) => num(b.quality) - num(a.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
    quality_asc: (a, b) => num(a.quality) - num(b.quality) || text(a.relative_path).localeCompare(text(b.relative_path)),
    path_asc: (a, b) => sourcePath(a).localeCompare(sourcePath(b)),
    path_desc: (a, b) => sourcePath(b).localeCompare(sourcePath(a)),
    source_path_asc: (a, b) => sourcePath(a).localeCompare(sourcePath(b)),
    source_path_desc: (a, b) => sourcePath(b).localeCompare(sourcePath(a)),
    source_mtime_desc: (a, b) => sourceMtime(b) - sourceMtime(a) || sourcePath(a).localeCompare(sourcePath(b)),
    source_mtime_asc: (a, b) => sourceMtime(a) - sourceMtime(b) || sourcePath(a).localeCompare(sourcePath(b)),
    category_asc: (a, b) => text(a.category).localeCompare(text(b.category)) || num(b.quality) - num(a.quality),
    category_desc: (a, b) => text(b.category).localeCompare(text(a.category)) || num(b.quality) - num(a.quality),
    status_asc: (a, b) => text(a.status).localeCompare(text(b.status)) || num(b.quality) - num(a.quality),
    status_desc: (a, b) => text(b.status).localeCompare(text(a.status)) || num(b.quality) - num(a.quality),
    kind_asc: (a, b) => text(a.document_kind).localeCompare(text(b.document_kind)) || num(b.quality) - num(a.quality),
    kind_desc: (a, b) => text(b.document_kind).localeCompare(text(a.document_kind)) || num(b.quality) - num(a.quality),
    sensitivity_asc: (a, b) => num(a.sensitivity_risk) - num(b.sensitivity_risk) || num(b.quality) - num(a.quality),
    sensitivity_desc: (a, b) => num(b.sensitivity_risk) - num(a.sensitivity_risk) || num(b.quality) - num(a.quality),
    public_desc: (a, b) => num(b.public_writing_suitability) - num(a.public_writing_suitability) || num(b.quality) - num(a.quality),
    public_asc: (a, b) => num(a.public_writing_suitability) - num(b.public_writing_suitability) || num(b.quality) - num(a.quality)
  };
  sorted.sort(comparators[key] || comparators.quality_desc);
  return sorted;
}

function renderSortMarks() {
  document.querySelectorAll("[data-sort-mark]").forEach(item => item.textContent = "");
  const map = {
    quality_desc: ["quality", "↓"],
    quality_asc: ["quality", "↑"],
    path_asc: ["path", "↑"],
    path_desc: ["path", "↓"],
    source_path_asc: ["path", "↑"],
    source_path_desc: ["path", "↓"],
    source_mtime_desc: ["source_mtime", "↓"],
    source_mtime_asc: ["source_mtime", "↑"],
    category_asc: ["category", "↑"],
    category_desc: ["category", "↓"],
    status_asc: ["status", "↑"],
    status_desc: ["status", "↓"],
    kind_asc: ["document_kind", "↑"],
    kind_desc: ["document_kind", "↓"],
    sensitivity_asc: ["sensitivity", "↑"],
    sensitivity_desc: ["sensitivity", "↓"],
    public_desc: ["sensitivity", tr("sort_public_desc")],
    public_asc: ["sensitivity", tr("sort_public_asc")]
  };
  const mark = map[sortKey];
  if (!mark) return;
  const target = document.querySelector(`[data-sort-mark="${mark[0]}"]`);
  if (target) target.textContent = mark[1];
}

function pageCountFor(total) {
  return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
}

function setPage(page) {
  if (!Number.isFinite(page)) return;
  currentPage = Math.min(Math.max(Math.floor(page), 1), pageCountFor(filteredRows.length));
  renderPager();
  renderPageRows();
}

function setPageSize(value) {
  if (!Number.isFinite(value) || value < 1) return;
  pageSize = Math.max(1, Math.floor(value));
  localStorage.setItem("doctriage_page_size", String(pageSize));
  currentPage = 1;
  renderPager();
  renderPageRows();
}

function rowExplanation(row) {
  const parts = [];
  const summary = String(row.summary || "").trim();
  const reason = String(row.reason || "").trim();
  if (summary) parts.push(`${tr("explain_summary")}: ${summary}`);
  if (reason) parts.push(`${tr("explain_reason")}: ${reason}`);
  const dimensions = EXPLANATION_DIMENSIONS
    .map(([field, labelKey]) => {
      const value = Number(row[field]);
      if (!Number.isFinite(value) || value <= 0) return "";
      return `${tr(labelKey)} ${value}`;
    })
    .filter(Boolean);
  if (dimensions.length) parts.push(`${tr("explain_dimensions")}: ${dimensions.join(" / ")}`);
  if (row.failure) {
    const failureParts = [];
    if (row.failure_stage) failureParts.push(`${tr("explain_failure_stage")} ${row.failure_stage}`);
    if (row.failure_reason) failureParts.push(`${tr("explain_failure_reason")} ${row.failure_reason}`);
    if (row.attempts) failureParts.push(`${tr("explain_failure_attempts")} ${row.attempts}`);
    if (row.failure_error && row.failure_error !== summary) {
      failureParts.push(`${tr("explain_failure_error")} ${row.failure_error}`);
    }
    if (failureParts.length) parts.push(`${tr("explain_failure")}: ${failureParts.join(" / ")}`);
  }
  return parts.join("\n");
}

function renderRows(rows) {
  readingRowsLoading = false;
  $("rows").setAttribute("aria-busy", "false");
  $("rows").removeAttribute("aria-label");
  $("rows").innerHTML = rows.map(row => {
    const explanation = rowExplanation(row);
    return `
    <tr>
      <td>${isPureFailureRow(row) ? "" : `<input type="checkbox" class="rowcheck" value="${escapeHtml(row.relative_path)}" />`}</td>
      <td class="status-${escapeAttr(row.status)}">${labelStatus(row.status)}</td>
      <td>${formatQuality(row)}</td>
      <td class="document-profile">${formatDocumentProfile(row)}</td>
      <td class="name">
        <span class="doc-name ${explanation ? "has-summary" : ""}" tabindex="${explanation ? "0" : "-1"}" data-tip="${escapeAttrValue(explanation)}">${escapeHtml(row.relative_path || "")}</span>
        ${row.source_path ? `<span class="doc-path">${escapeHtml(row.source_path)}</span>` : ""}
        ${row.note ? `<br><span class="muted">${escapeHtml(row.note)}</span>` : ""}
      </td>
      <td>${escapeHtml(row.source_mtime_label || "")}${row.source_size_label ? `<br><span class="muted">${escapeHtml(row.source_size_label)}</span>` : ""}</td>
      <td>${escapeHtml((row.topic_tags || []).join(", "))}</td>
      <td class="actions-cell"><div class="actions">${renderRowActions(row)}</div></td>
    </tr>`;
  }).join("");
  bindSummaryTooltips();
}

function isPureFailureRow(row) {
  return row.failure && !row.source_scope;
}

function formatQuality(row) {
  return Number.isFinite(Number(row.quality)) && row.quality !== null && row.quality !== undefined ? escapeHtml(row.quality) : "—";
}

function displayCategory(row) {
  if (row.category) return row.category;
  return row.source_only ? tr("scope_source_unscored") : "";
}

function displayKind(row) {
  if (row.document_kind && row.document_kind !== "Unscored") return row.document_kind;
  return row.source_only ? tr("scope_source_unscored") : (row.document_kind || "");
}

function formatDocumentProfile(row) {
  if (row.failure && !row.source_scope) return "—";
  const category = displayCategory(row);
  const kind = displayKind(row);
  const hasScores = row.sensitivity_risk !== null
    && row.sensitivity_risk !== undefined
    && row.public_writing_suitability !== null
    && row.public_writing_suitability !== undefined;
  const scores = hasScores
    ? `${tr("sensitivity_compact")} ${escapeHtml(row.sensitivity_risk)} · ${tr("public_compact")} ${escapeHtml(row.public_writing_suitability)}`
    : "";
  const parts = [
    category ? `<span class="profile-category">${escapeHtml(category)}</span>` : "",
    kind ? `<span class="profile-kind">${escapeHtml(kind)}</span>` : "",
    scores ? `<span class="profile-scores">${scores}</span>` : ""
  ].filter(Boolean);
  return parts.join("") || "—";
}

function renderRowActions(row) {
  if (isPureFailureRow(row)) {
    const missing = row.exists === false;
    const missingTitle = missing ? ` title='${escapeAttrValue(tr("missing_source_title"))}'` : "";
    return `
      <button ${missing || capabilities.open_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_open_title"))}'`}` : ""} onclick='openFailure(${JSON.stringify(row.source_path)})'>${tr("open")}</button>
      <button ${missing || capabilities.reveal_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_reveal_title"))}'`}` : ""} onclick='revealFailure(${JSON.stringify(row.source_path)})'>${tr("reveal")}</button>
    `;
  }
  const missing = row.exists === false;
  const missingTitle = missing ? ` title='${escapeAttrValue(tr("missing_source_title"))}'` : "";
  return `
    <button ${missing || capabilities.open_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_open_title"))}'`}` : ""} onclick='openDoc(${JSON.stringify(row.relative_path)})'>${tr("open")}</button>
    <button ${missing || capabilities.reveal_file === false ? `disabled${missingTitle || ` title='${escapeAttrValue(tr("disabled_reveal_title"))}'`}` : ""} onclick='revealDoc(${JSON.stringify(row.relative_path)})'>${tr("reveal")}</button>
    <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "reading")'>${tr("mark_reading")}</button>
    <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "read")'>${tr("mark_read")}</button>
    <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "deferred")'>${tr("mark_deferred")}</button>
    <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "skipped")'>${tr("mark_skipped")}</button>
    <button onclick='markDoc(${JSON.stringify(row.relative_path)}, "unread")'>${tr("mark_unread")}</button>
  `;
}

async function markDoc(relativePath, status) {
  const note = status === "read" ? "" : "";
  const response = await fetch("/api/mark", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({relative_path: relativePath, status, note, ...readingPathPayload()})
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("mark_failed"));
  showToast(trf("marked_status", {status: labelStatus(status)}));
  loadRows();
}

function selectedPaths() {
  return Array.from(document.querySelectorAll(".rowcheck:checked")).map(item => item.value);
}

function toggleAllRows(checked) {
  document.querySelectorAll(".rowcheck").forEach(item => item.checked = checked);
}

async function bulkMark(status) {
  const paths = selectedPaths();
  if (!paths.length) return showToast(tr("select_documents_first"));
  const response = await fetch("/api/mark-batch", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({relative_paths: paths, status, ...readingPathPayload()})
  });
  const payload = await response.json();
  if (!response.ok) return showToast(payload.error || tr("bulk_mark_failed"));
  showToast(trf("bulk_marked", {count: payload.count || 0}));
  loadRows();
}

function openNextVisible() {
  const row = currentRows.find(item => item.status === "unread" || item.status === "reread_needed") || currentRows[0];
  if (!row) return showToast(tr("current_list_empty"));
  openDoc(row.relative_path);
}

async function openDoc(relativePath) {
  await postAction("/api/open", relativePath, tr("requested_open"));
}

async function revealDoc(relativePath) {
  await postAction("/api/reveal", relativePath, tr("requested_reveal"));
}

async function openFailure(sourcePath) {
  await postSourceAction("/api/open-failure", sourcePath, tr("requested_open"));
}

async function revealFailure(sourcePath) {
  await postSourceAction("/api/reveal-failure", sourcePath, tr("requested_reveal"));
}

async function postAction(url, relativePath, okText) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({relative_path: relativePath, ...readingPathPayload()})
  });
  const payload = await response.json();
  showToast(response.ok ? okText : (payload.error || tr("operation_failed")));
}

async function postSourceAction(url, sourcePath, okText) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({source_path: sourcePath, ...readingPathPayload()})
  });
  const payload = await response.json();
  showToast(response.ok ? okText : (payload.error || tr("operation_failed")));
}

function labelStatus(status) {
  return {
    unread: tr("status_unread"),
    reading: tr("status_reading"),
    read: tr("status_read"),
    reread_needed: tr("status_reread_needed"),
    failed: tr("status_failed"),
    skipped: tr("status_skipped"),
    deferred: tr("status_deferred")
  }[status] || status;
}

function showToast(text) {
  const toast = $("toast");
  window.clearTimeout(showToast.timer);
  toast.textContent = text;
  toast.classList.add("show");
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function hideHelpTooltip() {
  tooltipTarget = null;
  $("tooltip").style.display = "none";
}

function positionHelpTooltip(target) {
  const tooltip = $("tooltip");
  const tip = target && target.dataset ? String(target.dataset.tip || "") : "";
  if (!tip) {
    hideHelpTooltip();
    return;
  }
  tooltip.textContent = tip;
  tooltip.style.display = "block";
  tooltip.style.visibility = "hidden";
  const margin = 12;
  tooltip.style.maxWidth = Math.min(320, Math.max(180, window.innerWidth - margin * 2)) + "px";
  const targetRect = target.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  const gap = 10;
  const left = Math.min(
    Math.max(margin, targetRect.left + targetRect.width / 2 - tooltipRect.width / 2),
    window.innerWidth - tooltipRect.width - margin
  );
  const spaceAbove = targetRect.top - margin;
  const spaceBelow = window.innerHeight - targetRect.bottom - margin;
  const top = spaceAbove >= tooltipRect.height + gap || spaceAbove >= spaceBelow
    ? Math.max(margin, targetRect.top - tooltipRect.height - gap)
    : Math.min(window.innerHeight - tooltipRect.height - margin, targetRect.bottom + gap);
  tooltip.style.left = left + "px";
  tooltip.style.top = top + "px";
  tooltip.style.visibility = "visible";
}

function showHelpTooltip(target) {
  tooltipTarget = target;
  positionHelpTooltip(target);
}

function refreshHelpTooltip() {
  if (tooltipTarget) positionHelpTooltip(tooltipTarget);
}

function bindSummaryTooltips(root = document) {
  root.querySelectorAll("[data-tip]").forEach(item => {
    if (item.dataset.tooltipBound === "1") return;
    item.dataset.tooltipBound = "1";
    item.addEventListener("mouseenter", () => showHelpTooltip(item));
    item.addEventListener("mouseleave", hideHelpTooltip);
    item.addEventListener("focus", () => showHelpTooltip(item));
    item.addEventListener("blur", hideHelpTooltip);
  });
}

function initHelpTooltips() {
  bindSummaryTooltips();
  window.addEventListener("scroll", hideHelpTooltip, true);
  window.addEventListener("resize", refreshHelpTooltip);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

function escapeAttr(value) {
  return String(value ?? "").replace(/[^a-zA-Z0-9_-]/g, "_");
}

function escapeAttrValue(value) {
  return escapeHtml(value);
}

function initReadingControls() {
  const scopeSelect = $("reading_scope");
  if (scopeSelect) {
    scopeSelect.value = readingScope;
    scopeSelect.addEventListener("change", () => {
      const previousScope = readingScope;
      readingScope = scopeSelect.value || "analysis";
      localStorage.setItem("doctriage_reading_scope", readingScope);
      sortKey = localStorage.getItem(sortStorageKey(readingScope)) || defaultSortForScope(readingScope);
      currentPage = 1;
      loadRows();
    });
  }
  for (const id of ["status","min_quality","q","max_sensitivity_risk","min_public_writing_suitability","categories","topic_tags"]) {
    const element = $(id);
    if (!element) continue;
    element.addEventListener("change", () => {
      currentPage = 1;
      applyClientFilters();
    });
  }
  $("q").addEventListener("input", () => {
    currentPage = 1;
    applyClientFilters();
  });
}

function initGraphControls() {
  for (const id of ["graph_q", "graph_min_size"]) {
    const element = $(id);
    if (!element) continue;
    const eventName = id === "graph_q" ? "input" : "change";
    element.addEventListener(eventName, () => applyGraphFilters(true));
  }
}

initReadingControls();
initGraphControls();
initUploadControls();
initRunFormPersistence();
initSharedTargetPersistence();
initReadingTargetPersistence();
initGraphTargetPersistence();
initRagTargetPersistence();
initAnydocsTargetPersistence();
initHelpTooltips();
applyStoredRunFormState();
const readingApplied = applyStoredReadingTargetState();
const graphApplied = applyStoredGraphTargetState();
const ragApplied = applyStoredRagTargetState();
const anydocsApplied = applyStoredAnydocsTargetState();
if (!readingApplied) syncReadingTargetFromRunOutput({force: true, syncGraph: !graphApplied, syncAnydocs: !anydocsApplied});
if (!graphApplied) syncGraphTargetFromReadingOutput({force: true, syncAnydocs: !anydocsApplied});
if (!ragApplied) syncRagTargetFromReadingOutput({force: true});
if (!anydocsApplied) syncAnydocsTargetFromGraphOutput({force: true});
normalizeSharedTargetFromTargets({persist: true});
clearGraphState("empty_graph");
clearRagState("rag_no_index");
applyI18n();

async function bootstrap() {
  try {
    await loadConfig();
  } catch (error) {
    showToast(error?.message || tr("operation_failed"));
  }
  switchTab(localStorage.getItem("doctriage_tab") || "analysis");
}

bootstrap();
setInterval(() => {
  if ($("section-analysis").classList.contains("active")) loadAnalysis();
  if ($("section-graph").classList.contains("active") && graphMeta && graphMeta.task && graphMeta.task.running) loadGraph();
  if ($("section-rag").classList.contains("active")) loadRagStatus();
}, 3000);
