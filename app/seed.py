"""mock 数据：SDM 仿真任务 / 报告结构化模板 / 按任务类型持久化的标准二维表。

- 任务数据与 apps/server/app/seed_data.py 风格一致，字段按
  docs/cae智能体与工作流设计.md 主流程第 2 步要求组织：
  任务名称(含 PDCA 字样)、任务单编号、报告编号、编制/校对/审核/批准、
  日期、项目号、关联工作区文档信息。
- 模板结构（blocks/binds）与 apps/web-v2/src/data/reportTemplate.ts 的
  ReportDoc 同构，来源 docs/结构强度模板/cae_结构强度.md。
"""

from __future__ import annotations

# ---------------------------------------------------------------- SDM 仿真任务

SDM_TASKS: list[dict] = [
    {
        "task_id": "SDM-SIM-2026-1187",
        "task_name": "D320随车吊TL2A车架强度分析",
        "task_no": "QT21060801",
        "report_no": "332820-xxx-2026",
        "project_no": "A20CTDE",
        "project_name": "D320随车吊开发项目",
        "platform": "D320",
        "vehicle_model": "D320随车吊",
        "analysis_object": "TL2A车架",
        "part_no": "TL2A",
        "date": "2026-10-20",
        "deadline": "2026-11-05",
        "status": "待处理",
        "assignee": "李智勇",
        "authors": {"编制": "李智勇", "校对": "王辉", "审核": "刘道勇", "批准": "成杏林"},
        "analysis_software": "HyperWorks 2023.0",
        "workspace_docs": [
            {"name": "Q/DFM CV 001 车架强度分析规范", "doc_type": "企业标准", "size_kb": 812, "updated": "2024-03-02"},
            {"name": "TL2A车架有限元模型说明_v3.2", "doc_type": "模型文档", "size_kb": 2400, "updated": "2026-10-11"},
            {"name": "D320-STR-018 车架强度分析报告（历史）", "doc_type": "历史报告", "size_kb": 5120, "updated": "2021-10-25"},
        ],
    },
    {
        "task_id": "SDM-SIM-2026-1201",
        "task_name": "D320随车吊TL2A车架强度分析（PDCA整改复核）",
        "task_no": "QT21070215",
        "report_no": "332820-xxx-2026-PDCA",
        "project_no": "A20CTDE",
        "project_name": "D320随车吊开发项目",
        "platform": "D320",
        "vehicle_model": "D320随车吊",
        "analysis_object": "TL2A车架",
        "part_no": "TL2A",
        "date": "2026-10-24",
        "deadline": "2026-11-10",
        "status": "待处理",
        "assignee": "李智勇",
        "authors": {"编制": "李智勇", "校对": "王辉", "审核": "刘道勇", "批准": "成杏林"},
        "analysis_software": "HyperWorks 2023.0",
        "workspace_docs": [
            {"name": "Q/DFM CV 001 车架强度分析规范", "doc_type": "企业标准", "size_kb": 812, "updated": "2024-03-02"},
            {"name": "外加强板吊点区域圆角优化方案", "doc_type": "设计变更", "size_kb": 660, "updated": "2026-10-18"},
        ],
    },
    {
        "task_id": "SDM-SIM-2026-1244",
        "task_name": "D320随车吊TL2A车架刚度分析",
        "task_no": "QT21070301",
        "report_no": "332820-STI-2026-057",
        "project_no": "A20CTDE",
        "project_name": "D320随车吊开发项目",
        "platform": "D320",
        "vehicle_model": "D320随车吊",
        "analysis_object": "TL2A车架",
        "part_no": "TL2A",
        "date": "2026-10-26",
        "deadline": "2026-11-12",
        "status": "待处理",
        "assignee": "王辉",
        "authors": {"编制": "王辉", "校对": "李智勇", "审核": "刘道勇", "批准": "成杏林"},
        "analysis_software": "HyperWorks 2023.0",
        "workspace_docs": [
            {"name": "Q/DFM CV 002 车架刚度分析规范", "doc_type": "企业标准", "size_kb": 730, "updated": "2024-05-11"},
        ],
    },
    {
        "task_id": "SDM-SIM-2026-1252",
        "task_name": "X23驾驶室正面碰撞分析",
        "task_no": "CAE-CRASH-24052",
        "report_no": "332820-CRS-2026-052",
        "project_no": "X23-2026-0019",
        "project_name": "X23驾驶室开发项目",
        "platform": "X23",
        "vehicle_model": "X23载货车",
        "analysis_object": "X23驾驶室",
        "part_no": "CAB-X23",
        "date": "2026-10-25",
        "deadline": "2026-11-20",
        "status": "待处理",
        "assignee": "李智勇",
        "authors": {"编制": "李智勇", "校对": "周工", "审核": "赵总", "批准": "成杏林"},
        "analysis_software": "LS-DYNA",
        "workspace_docs": [
            {"name": "GB 26512 商用车驾驶室乘员保护要求", "doc_type": "国标", "size_kb": 1180, "updated": "2021-05-01"},
        ],
    },
    {
        "task_id": "SDM-SIM-2026-1219",
        "task_name": "EV7电池包一阶模态避频分析",
        "task_no": "CAE-MOD-24013",
        "report_no": "332820-MOD-2026-013",
        "project_no": "EV-2026-0007",
        "project_name": "EV7滑板平台电池系统集成",
        "platform": "EV7",
        "vehicle_model": "EV7滑板平台",
        "analysis_object": "电池包总成",
        "part_no": "BP-EV7",
        "date": "2026-09-30",
        "deadline": "2026-10-15",
        "status": "已完成",
        "assignee": "李慧勇",
        "authors": {"编制": "李慧勇", "校对": "陈工", "审核": "赵总", "批准": "成杏林"},
        "analysis_software": "ABAQUS 2023",
        "workspace_docs": [
            {"name": "电池包模态分析规范", "doc_type": "企业标准", "size_kb": 540, "updated": "2025-01-20"},
        ],
    },
]


def find_task(task_id: str) -> dict | None:
    return next((t for t in SDM_TASKS if t["task_id"] == task_id), None)


# ---------------------------------------------------------------- 报告结构化模板
#
# block 结构与 web-v2 ReportDoc 同构，另加 `bind`/`source` 表达取数来源：
#   infoTable.rows[i].bind —— 值的绑定路径（docgen 按 ctx 解析，缺省渲染“（待补充）”）
#   table.bind             —— 行数据绑定（二维表，行数组由 docgen 派生）
#   figure.bind            —— 绑定为图片 URL 或 [{caption,url}] 列表
#   list.bind              —— 绑定为字符串数组
#   paragraph.bind         —— 绑定为字符串（支持 \n 多段）
# 静态文本直接写 value/text/items。

STRENGTH_TEMPLATE: dict = {
    "template_id": "cae_strength_report_v1",
    "name": "CAE 结构强度分析报告模板",
    "task_type": "结构强度",
    "task_type_code": "strength",
    "version": "v1",
    "org": "东风商用车有限公司技术中心",
    "doc_type": "CAE 分析报告",
    "signatures": [{"role": "编制"}, {"role": "校对"}, {"role": "审核"}, {"role": "批准"}],
    "sections": [
        {
            "id": "s1",
            "number": "1",
            "title": "分析总体情况",
            "note": "本表单独占一页",
            "blocks": [
                {
                    "kind": "infoTable",
                    "rows": [
                        {"label": "项目号", "bind": "task.project_no", "half": True},
                        {"label": "任务单编号", "bind": "task.task_no", "half": True},
                        {"label": "报告编号", "bind": "task.report_no", "half": True},
                        {"label": "日期", "bind": "task.date", "half": True},
                        {"label": "分析目的", "bind": "report.analysis_purpose"},
                        {"label": "分析项目及方法", "bind": "report.analysis_method"},
                        {"label": "分析结论", "bind": "report.analysis_conclusion"},
                        {"label": "备注", "value": ""},
                    ],
                }
            ],
        },
        {
            "id": "s2",
            "number": "2",
            "title": "分析载荷与边界条件",
            "blocks": [],
            "children": [
                {
                    "id": "s2-1",
                    "number": "2.1",
                    "title": "分析模型",
                    "blocks": [
                        {"kind": "paragraph", "text": "分析采用有限元模型如下图所示。"},
                        {"kind": "figure", "label": "图1", "caption": "分析模型", "bind": "report.model_figures",
                         "source": "压缩包截图/模型图片（文件名含“模型”或“model”）"},
                    ],
                },
                {
                    "id": "s2-2",
                    "number": "2.2",
                    "title": "分析工况/边界",
                    "blocks": [
                        {"kind": "list", "bind": "report.condition_items",
                         "source": "标准/历史报告改写；工况清单由二次处理结果表列头汇总"},
                        {"kind": "figure", "label": "图2", "caption": "载荷与边界条件",
                         "bind": "report.load_figures",
                         "source": "压缩包图片：文件名含「载荷」"},
                    ],
                },
                {
                    "id": "s2-3",
                    "number": "2.3",
                    "title": "材料信息",
                    "blocks": [
                        {
                            "kind": "table",
                            "label": "表0",
                            "caption": "部件材料信息",
                            "columns": ["部件名称", "材料名称", "屈服强度（MPa）", "安全系数"],
                            "bind": "report.material_table",
                            "source": "部件/材料由二次处理结果给出；屈服强度/安全系数取标准持久化数据（材料库）",
                        }
                    ],
                },
            ],
        },
        {
            "id": "s3",
            "number": "3",
            "title": "分析结果",
            "blocks": [
                {"kind": "paragraph", "text": "3.1 强度分析结果见表1，应力云图见图3。"},
                {
                    "kind": "table",
                    "label": "表1",
                    "caption": "强度分析结果（单位：MPa）",
                    "columns": ["部位", "工况", "最大应力（MPa）", "许用应力（MPa）", "判定"],
                    "bind": "report.stress_table",
                    "source": "二次处理结果表（压缩包解析）",
                },
                {
                    "kind": "figure",
                    "label": "图3",
                    "caption": "分析结果应力云图（单位：MPa）",
                    "bind": "report.result_figures",
                    "source": "压缩包其余图片（除载荷图/模型图/改善方案图外全部）",
                },
                {
                    "kind": "table",
                    "label": "表2",
                    "caption": "非标工况应力峰值（单位：MPa）",
                    "columns": ["工况", "部位", "应力峰值（MPa）"],
                    "bind": "report.nonstd_table",
                    "source": "二次处理结果表（非标工况列）",
                },
            ],
        },
        {
            "id": "s4",
            "number": "4",
            "title": "结果分析及建议",
            "blocks": [
                {"kind": "paragraph", "bind": "report.conclusion_paragraphs",
                 "source": "由判定结果确定性生成（初版），正式版由智能体改写"},
                {
                    "kind": "table",
                    "label": "表3",
                    "caption": "改善方案应力峰值（单位：MPa）",
                    "columns": ["方案", "部位", "应力峰值（MPa）"],
                    "bind": "report.improve_table",
                    "source": "改善方案数据（如压缩包未提供则待补充）",
                },
                {
                    "kind": "figure",
                    "label": "图4",
                    "caption": "改善方案应力云图",
                    "bind": "report.improve_figures",
                    "source": "改善方案截图（如压缩包未提供则待补充）",
                },
            ],
        },
        {
            "id": "s5",
            "number": "5",
            "title": "附录",
            "blocks": [],
            "children": [
                {"id": "s5-1", "number": "5.1", "title": "分析对象",
                 "blocks": [{"kind": "paragraph", "bind": "task.analysis_object"}]},
                {"id": "s5-2", "number": "5.2", "title": "分析内容",
                 "blocks": [{"kind": "paragraph", "bind": "report.analysis_scope"}]},
                {"id": "s5-3", "number": "5.3", "title": "分析软件与时间",
                 "blocks": [{"kind": "paragraph", "bind": "report.software_and_time"}]},
                {"id": "s5-4", "number": "5.4", "title": "分析人员",
                 "blocks": [{"kind": "list", "bind": "report.staff_items"}]},
            ],
        },
    ],
}

TEMPLATES: list[dict] = [STRENGTH_TEMPLATE]


def find_template(template_id: str) -> dict | None:
    return next((t for t in TEMPLATES if t["template_id"] == template_id), None)


def find_template_by_task_type(task_type_code: str) -> dict | None:
    return next((t for t in TEMPLATES if t["task_type_code"] == task_type_code), None)


# ---------------------------------------------------------------- 标准二维表（按任务类型持久化）
#
# 需求主流程第 5 条：一类任务的标准信息持久化复用，不每次从标准文档提取。
# 首次启动自动写入 data/standards/strength.json，之后可通过 PUT 接口更新（版本自增）。
# ⚠️ 以下系数与屈服强度均为示例数据，正式值以企标条款/材料库提取结果为准。

DEFAULT_STANDARDS: list[dict] = [
    {
        "task_type": "结构强度",
        "task_type_code": "strength",
        "name": "车架强度分析工况系数与材料屈服强度（企业标准）",
        "source": "示例数据（模拟自 Q/DFM CV 001 条款提取，待替换为真实企标提取结果）",
        "version": 1,
        "condition_factors": [
            {"condition": "弯曲", "factor": 1.3, "clause": "表2"},
            {"condition": "扭转", "factor": 1.3, "clause": "表2"},
            {"condition": "转弯", "factor": 1.1, "clause": "表3"},
            {"condition": "扭转+转弯", "factor": 1.1, "clause": "表3"},
            {"condition": "制动", "factor": 1.1, "clause": "表4"},
            {"condition": "双扭", "factor": 1.0, "clause": "表4"},
        ],
        "material_yields": [
            {"material": "DL590", "name": "590L", "yield_mpa": 430.0},
            {"material": "DL591", "name": "610L", "yield_mpa": 355.0},
            {"material": "DL592", "name": "610L", "yield_mpa": 355.0},
            {"material": "DL593", "name": "520L", "yield_mpa": 330.0},
            {"material": "DL594", "name": "420L", "yield_mpa": 255.0},
            {"material": "DL595", "name": "610L", "yield_mpa": 355.0},
        ],
    }
]
