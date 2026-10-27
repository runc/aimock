"""任务类型解析：从 SDM 任务名称推导学科/任务类型与 PDCA 标记。

需求依据 docs/cae智能体与工作流设计.md：任务类型通过任务名称解析而来。
仿真业务共八个学科（结构、安全、疲劳、模态、振动、碰撞等），本阶段仅
「结构强度」具备完整模板与判定链路，其余类型可解析但报告生成暂不支持。
"""

from __future__ import annotations

import re
from typing import Any

# 关键词 → (任务类型中文名, 类型码, 学科)。顺序即优先级：碰撞在安全前，避免“碰撞安全”误判。
TASK_TYPE_RULES: list[tuple[str, list[str], str, str]] = [
    ("结构强度", ["强度"], "strength", "结构"),
    ("结构刚度", ["刚度"], "stiffness", "结构"),
    ("疲劳", ["疲劳", "耐久"], "fatigue", "疲劳"),
    ("模态", ["模态", "避频", "频率"], "modal", "模态"),
    ("振动", ["振动", "nvh"], "vibration", "振动"),
    ("碰撞", ["碰撞", "crash"], "crash", "碰撞"),
    ("安全", ["安全"], "safety", "安全"),
    ("操稳", ["操稳", "操纵稳定", "平顺"], "handling", "操稳"),
]

# 结构强度标准工况集合（判定“非标工况”用）；凡不在集合内的工况（如 吊点X向）为非标
STANDARD_CONDITIONS = ["弯曲", "扭转", "转弯", "扭转+转弯", "制动", "双扭"]


def parse_task_type(task_name: str) -> dict[str, Any]:
    """从任务名称解析任务类型。

    返回：{"task_type": "结构强度", "task_type_code": "strength",
           "discipline": "结构", "supported": true, "pdca": false}
    无法识别时 task_type=None / code="other" / supported=False。
    """
    name = task_name or ""
    lowered = name.lower()
    pdca = "pdca" in lowered

    task_type, code, discipline = None, "other", None
    for type_name, keywords, type_code, disc in TASK_TYPE_RULES:
        if any(k in lowered for k in keywords):
            task_type, code, discipline = type_name, type_code, disc
            break

    return {
        "task_type": task_type,
        "task_type_code": code,
        "discipline": discipline,
        "supported": code == "strength",  # 本阶段仅结构强度有模板与判定链路
        "pdca": pdca,
    }


def is_standard_condition(condition: str) -> bool:
    """工况是否属于结构强度标准工况（用于区分非标工况）。"""
    return condition in STANDARD_CONDITIONS


# ---- 工况列名归一化：二次处理表列名存在中英混写（弯曲工况 bend / 吊点X向工况（非标）） ----

_EN_CONDITION_TOKENS: list[tuple[str, str]] = [
    ("bend", "弯曲"),
    ("torsion1", "扭转"),
    ("torsion", "扭转"),
    ("tor+cor", "扭转+转弯"),
    ("cornering", "转弯"),
    ("brake", "制动"),
    ("bad", "双扭"),
    ("doubletorsion", "双扭"),
]


def normalize_condition(column_name: str) -> str:
    """工况列名 → 规范工况名：去掉英文后缀、去掉“工况”字样与非标括号。

    例：弯曲工况 bend→弯曲；吊点X向工况（非标）→吊点X向；扭转+转弯工况 tor+cor→扭转+转弯。
    """
    name = (column_name or "").strip()
    # 去掉中英文括号备注，如 （非标）
    name = re.sub(r"[（(][^）)]*[）)]", "", name).strip()
    # 英文 token 映射（列名常为 “中文 工况 english”）
    lowered = name.lower()
    for token, std in _EN_CONDITION_TOKENS:
        if token in lowered:
            return std
    # 去掉结尾“工况”字样
    if name.endswith("工况"):
        name = name[: -len("工况")]
    return name.strip() or column_name
