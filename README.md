# CAE 仿真报告智能体 server-v2（mock 服务集）

对应设计文档《cae智能体与工作流设计.md》（monorepo `docs/` 目录）的 mock 服务实现：
FastAPI + uv，**无数据库、零外部依赖**（文件即存储），供擎天智能体平台的编排工作流以
HTTP 节点调用。与 `apps/server`（上一代 LangGraph 完整后端）相互独立，不复用代码。

## 服务清单

| 需求 | 服务 | 接口 | 说明 |
| --- | --- | --- | --- |
| a | SDM 任务信息 | `GET /api/sdm/tasks?user=李智勇&status=待处理`<br>`GET /api/sdm/tasks/{task_id}` | 信息收集节点列任务 / HTTP 节点取基本信息（任务名称含 PDCA 检测、任务单编号、报告编号、编制/校对/审核/批准、日期、项目号、关联工作区文档） |
| b | 压缩包解析校验 | `POST /api/archive/parse`（multipart `file`） | zip/rar 解压（兼容 Windows 中文名）；csv/tsv/xlsx 表格解析；图片解析「部件-工况」命名并标注载荷图/模型图/改善方案图（报告第 2 章取文件名含「载荷」的图，第 3 章取其余图片）；兼容理想格式（单表）与分开格式（材料/应力/非标三表合并）；完整性校验（缺列/缺材料/非数值→errors，缺评价标准与安全系数→warnings 待确认） |
| c | Word 生成 | `POST /api/report/docx` | 输入任务信息（a）+ 解析结果（b）+ 可选标准，按模板（d）生成 DOCX 初版并返回下载地址；判定逻辑确定性完成（无 LLM） |
| d | 模板结构化信息 | `GET /api/templates`<br>`GET /api/templates/{template_id}`<br>`GET /api/templates/by-task-name?task_name=…` | 报告结构化模板（与 web-v2 右侧 `reportTemplate.ts` 同构，来源 docs/结构强度模板），block 以 `bind` 声明取数绑定 |
| — | 标准持久化 | `GET/PUT /api/standards/{task_type}` | 主流程第 5 条：一类任务的标准二维表（工况系数/材料屈服强度）持久化复用，JSON 存 `data/standards/`，首次启动自动写示例数据 |
| — | 静态文件 | `GET /files/uploads/**`、`GET /files/exports/**` | 上传的图片与生成的 docx 下载 |

**任务类型由任务名称解析**（`app/tasktype.py`）：强度→结构强度、刚度→结构刚度、
疲劳/模态/振动/碰撞/安全/操稳按关键词；`PDCA` 字样（不区分大小写）单独标记。
本阶段仅「结构强度」有模板与判定链路，其余类型 `by-task-name` 返回 404。

## 快速开始

```bash
cd apps/server-v2
uv sync                                                  # 安装依赖
uv run uvicorn app.main:app --reload --port 8200         # 或仓库根目录 npm run dev:server-v2
uv run python scripts/make_sample_archive.py             # 生成示例二次处理压缩包（理想格式）
uv run python scripts/smoke.py                           # 冒烟：a→b→d→e→c 全链路
uv run python scripts/test_edge_cases.py                 # 边界：分开格式/PDCA/损坏包/缺材料/无模板
```

交互式接口文档：http://127.0.0.1:8200/docs

## 生成 Word 的调用契约（c 服务）

```jsonc
POST /api/report/docx
{
  "task":   { /* 服务 a 的任务详情原样传入（至少含 task_name）*/ },
  "result": { /* 服务 b 的解析结果原样传入；缺省则全文档渲染「（待补充）」*/ },
  "template_id": "cae_strength_report_v1",   // 可选，缺省按 task_name 解析类型选模板
  "file_name": "xxx强度分析报告.docx",         // 可选
  "standard": { /* 可选，缺省按任务类型自动取 /api/standards 持久化数据 */ }
}
// 响应
{
  "file_url": "http://127.0.0.1:8200/files/exports/xxx.docx",
  "judge_summary": "存在不合格项：外加强板在「吊点X向」超限（353MPa > 326MPa）",
  "verdicts": { "rows": [...], "fail_count": 1, "pending_count": 0 },
  "warnings": ["…渲染时缺数据的位置…"]
}
```

判定优先级（`compute_verdicts`）：二次处理评价标准 > 安全系数×屈服强度 >
企标工况系数×屈服强度（仅标准工况）；无依据 → 待确认。非标工况（吊点X/Y 等）
不在企标系数表内，必须由二次处理给出评价标准或安全系数，否则进入待确认。

## 目录结构

```
app/
├── main.py        入口：路由/静态挂载/CORS/启动种子
├── config.py      端口（8200）与数据目录
├── tasktype.py    任务类型解析（任务名称→类型/PDCA）+ 工况列名归一化
├── sdm.py         a. SDM 任务信息
├── archive.py     b. 压缩包解析与校验
├── templates.py   d. 模板结构化信息
├── standards.py   标准二维表持久化（按任务类型）
├── docgen.py      c. Word 生成（判定 + 上下文派生 + python-docx 渲染）
└── seed.py        mock 数据（SDM 任务 / 模板 / 示例标准）
scripts/
├── make_sample_archive.py  示例压缩包（理想格式 + 占位云图）
├── smoke.py                冒烟测试
└── test_edge_cases.py      边界用例
data/                      运行时目录（gitignore）：uploads/ exports/ standards/ sample/
```

## 与真实环境的替换点

- `sdm.py`：替换为 SDM 系统真实接口（字段以现返回结构为准）。
- `archive.py`：可直用于真实二次处理压缩包；rar 依赖服务端安装 unrar 工具。
- `standards.py`：正式版为「知识库条款提取一次 + 落库」，PUT 接口即提取结果的写入通道。
- `docgen.py`：文字（分析目的/方法/结论）目前为固定句式初版，正式版由擎天工作流
  LLM 节点改写后回填（工作流暂未设计，见 docs/cae智能体与工作流设计.md）。
