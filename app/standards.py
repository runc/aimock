"""标准二维表持久化（按任务类型）。

对应主流程第 5 条：一类任务的标准信息（工况系数/材料屈服强度等二维表）
从标准文档提取一次后持久化复用，不每次重新提取。mock 阶段以 JSON 文件
存储于 data/standards/，首次启动自动写入内置示例；真实环境可替换为
知识库提取 + 数据库存储。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .seed import DEFAULT_STANDARDS
from .tasktype import TASK_TYPE_RULES

router = APIRouter(prefix="/api/standards", tags=["standards"])


class StandardPayload(BaseModel):
    name: str = Field(description="标准名称")
    source: str = Field(default="", description="来源说明（文档名/条款）")
    condition_factors: list[dict] = Field(default_factory=list,
                                          description="标准工况系数表 [{condition, factor, clause}]")
    material_yields: list[dict] = Field(default_factory=list,
                                        description="材料屈服强度表 [{material, name, yield_mpa}]")


def _type_code(task_type: str) -> str:
    """支持传 中文名（结构强度）或 类型码（strength）。"""
    lowered = task_type.strip().lower()
    for name, _kw, code, _disc in TASK_TYPE_RULES:
        if lowered == code or task_type.strip() == name:
            return code
    raise HTTPException(status_code=404, detail=f"未知的任务类型：{task_type}")


def _path(code: str) -> Path:
    return settings.standards_root / f"{code}.json"


def seed_if_missing() -> None:
    settings.standards_root.mkdir(parents=True, exist_ok=True)
    for std in DEFAULT_STANDARDS:
        p = _path(std["task_type_code"])
        if not p.exists():
            p.write_text(json.dumps({**std, "updated_at": _now()}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_standard(code: str) -> dict | None:
    p = _path(code)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("")
def list_standards():
    items = []
    for p in sorted(settings.standards_root.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        items.append({
            "task_type": data.get("task_type"),
            "task_type_code": data.get("task_type_code"),
            "name": data.get("name"),
            "version": data.get("version"),
            "updated_at": data.get("updated_at"),
            "condition_factors": len(data.get("condition_factors", [])),
            "material_yields": len(data.get("material_yields", [])),
        })
    return {"count": len(items), "items": items}


@router.get("/{task_type}")
def get_standard(task_type: str):
    code = _type_code(task_type)
    data = load_standard(code)
    if not data:
        raise HTTPException(status_code=404, detail=f"任务类型「{task_type}」暂无持久化标准，请先 PUT 录入")
    return {"mock": True, **data}


@router.put("/{task_type}")
def put_standard(task_type: str, payload: StandardPayload):
    code = _type_code(task_type)
    type_name = next(name for name, _kw, c, _d in TASK_TYPE_RULES if c == code)
    existing = load_standard(code) or {}
    data = {
        "task_type": type_name,
        "task_type_code": code,
        "name": payload.name,
        "source": payload.source,
        "version": int(existing.get("version", 0)) + 1,
        "updated_at": _now(),
        "condition_factors": payload.condition_factors,
        "material_yields": payload.material_yields,
    }
    _path(code).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"mock": True, "saved": True, **data}
