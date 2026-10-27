"""服务 a：SDM 仿真任务基本信息（mock）。

对应主流程第 0/1 步（信息收集节点列任务）与第 2 步（选定任务后 HTTP 节点
调 SDM 取基本信息）。真实环境替换为 SDM 系统接口。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .seed import SDM_TASKS, find_task
from .tasktype import parse_task_type

router = APIRouter(prefix="/api/sdm", tags=["sdm"])


def _brief(task: dict) -> dict:
    """列表项：信息收集节点展示用。任务类型由任务名称解析而来。"""
    parsed = parse_task_type(task["task_name"])
    return {
        "task_id": task["task_id"],
        "task_name": task["task_name"],
        "task_no": task["task_no"],
        "report_no": task["report_no"],
        "project_no": task["project_no"],
        "project_name": task["project_name"],
        "analysis_object": task["analysis_object"],
        "status": task["status"],
        "assignee": task["assignee"],
        "deadline": task["deadline"],
        "date": task["date"],
        "task_type": parsed["task_type"],
        "task_type_code": parsed["task_type_code"],
        "supported": parsed["supported"],
        "pdca": parsed["pdca"],
    }


def _detail(task: dict) -> dict:
    """任务详情：报告第一章/封面所需的全部基本信息。"""
    parsed = parse_task_type(task["task_name"])
    brief = _brief(task)
    return {
        **brief,
        "task_type_info": parsed,
        "platform": task["platform"],
        "vehicle_model": task["vehicle_model"],
        "part_no": task["part_no"],
        "authors": task["authors"],
        "author_signatures": [
            {"role": role, "name": name, "date": task["date"]}
            for role, name in task["authors"].items()
        ],
        "analysis_software": task["analysis_software"],
        "workspace_docs": task["workspace_docs"],
    }


@router.get("/tasks")
def list_tasks(
    user: str | None = Query(None, description="按当前用户过滤（assignee）"),
    status: str | None = Query("待处理", description="按状态过滤，传空返回全部"),
):
    tasks = SDM_TASKS
    if user:
        tasks = [t for t in tasks if t["assignee"] == user]
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    return {
        "count": len(tasks),
        "items": [_brief(t) for t in tasks],
        "mock": True,
    }


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = find_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"SDM 任务不存在：{task_id}")
    return {"mock": True, **_detail(task)}
