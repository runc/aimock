"""服务 d：报告模板结构化信息服务。

对应需求 1-d：把 word 文档结构以结构化信息表达（与 web-v2 右侧预览同构），
生成 Word 时按模板填充数据即可产出仿真任务文档。

block/bind 语义见 app/seed.py STRENGTH_TEMPLATE 注释。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .seed import TEMPLATES, find_template, find_template_by_task_type
from .tasktype import TASK_TYPE_RULES, parse_task_type

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _brief(t: dict) -> dict:
    return {
        "template_id": t["template_id"],
        "name": t["name"],
        "task_type": t["task_type"],
        "task_type_code": t["task_type_code"],
        "version": t["version"],
        "sections": len(t["sections"]),
    }


@router.get("")
def list_templates():
    return {"count": len(TEMPLATES), "items": [_brief(t) for t in TEMPLATES], "mock": True}


@router.get("/by-task-name")
def get_template_by_task_name(task_name: str = Query(..., description="SDM 任务名称，解析任务类型后匹配模板")):
    """任务类型由任务名称解析而来（需求约定），再按类型取模板。"""
    parsed = parse_task_type(task_name)
    template = find_template_by_task_type(parsed["task_type_code"])
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"任务「{task_name}」解析为类型「{parsed['task_type'] or '未识别'}」，暂无对应报告模板",
        )
    return {"mock": True, "task_type_info": parsed, **template}


@router.get("/{template_id}")
def get_template(template_id: str):
    template = find_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
    return {"mock": True, **template}


# 供内部模块（docgen）使用的类型清单
SUPPORTED_TASK_TYPES = [
    {"task_type": name, "task_type_code": code, "discipline": disc, "has_template": any(
        t["task_type_code"] == code for t in TEMPLATES)}
    for name, _kw, code, disc in TASK_TYPE_RULES
]
