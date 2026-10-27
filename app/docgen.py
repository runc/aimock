"""服务 c：按模板结构与样式生成 Word 文档。

对应需求 1-c 与主流程第 4 步：任务基本信息（服务 a）+ 二次处理结果（服务 b）
+ 持久化标准（/api/standards）→ 按结构化模板（服务 d）填充 → 生成 DOCX 初版。

生成链路全部确定性（无 LLM）：
- 判定逻辑：许用应力优先级 = 二次处理评价标准 > 安全系数×屈服强度 >
  企标工况系数×屈服强度（仅标准工况），无依据 → 待确认；
- 文字（分析目的/方法/结论）由任务信息+判定结果按固定句式生成初版，
  后续由擎天工作流 LLM 节点改写；
- 模板 block 的 bind 绑定到上下文，缺数据渲染「（待补充）」并记入 warnings。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .config import settings
from .seed import find_template, find_template_by_task_type
from .standards import load_standard
from .tasktype import is_standard_condition, parse_task_type

router = APIRouter(prefix="/api/report", tags=["report"])

GRAY = RGBColor(0x80, 0x80, 0x80)
BLACK = RGBColor(0, 0, 0)


class DocGenRequest(BaseModel):
    template_id: str | None = Field(None, description="模板 ID，如 cae_strength_report_v1")
    task_name: str | None = Field(None, description="任务名称（无 template_id 时按名称解析任务类型选模板）")
    file_name: str | None = Field(None, description="输出文件名，缺省按任务名生成")
    task: dict = Field(..., description="SDM 任务详情（服务 a /api/sdm/tasks/{id} 的返回）")
    result: dict | None = Field(None, description="压缩包解析结果（服务 b /api/archive/parse 的返回）")
    standard: dict | None = Field(None, description="标准二维表；缺省按任务类型自动取持久化标准")


# ---------------------------------------------------------------- 判定（确定性）

def _std_maps(standard: dict | None) -> tuple[dict[str, float], dict[str, dict]]:
    standard = standard or {}
    factors = {c["condition"]: float(c["factor"]) for c in standard.get("condition_factors", []) if c.get("factor")}
    yields = {m["material"]: m for m in standard.get("material_yields", [])}
    return factors, yields


def compute_verdicts(result_table: list[dict], standard: dict | None) -> dict:
    """逐部件×工况判定。返回 {rows, summary}，verdict ∈ 合格/不合格/待确认。"""
    factors, yields = _std_maps(standard)
    rows: list[dict] = []
    for item in result_table or []:
        material = item.get("material")
        yield_info = yields.get(material or "")
        yield_mpa = item.get("yield_mpa") or (yield_info or {}).get("yield_mpa")
        for condition, stress in (item.get("stresses") or {}).items():
            if stress is None:
                continue
            limit, basis = None, None
            if item.get("eval_standard_mpa"):
                limit, basis = float(item["eval_standard_mpa"]), "二次处理评价标准"
            elif item.get("safety_factor") and yield_mpa:
                limit = float(yield_mpa) / float(item["safety_factor"])
                basis = f"屈服强度{yield_mpa:g}MPa/安全系数{item['safety_factor']:g}"
            elif is_standard_condition(condition) and factors.get(condition) and yield_mpa:
                limit = float(yield_mpa) / factors[condition]
                basis = f"屈服强度{yield_mpa:g}MPa/企标工况系数{factors[condition]:g}"
            if limit is None:
                verdict, margin = "待确认", None
            else:
                verdict = "合格" if stress <= limit else "不合格"
                margin = round(limit - stress, 1)
            rows.append({
                "part": item["part"], "material": material, "condition": condition,
                "stress_mpa": stress, "limit_mpa": round(limit, 1) if limit is not None else None,
                "basis": basis, "verdict": verdict,
                "exceed_ratio": round((stress - limit) / limit * 100, 1) if verdict == "不合格" else None,
                "margin_mpa": margin,
            })

    fails = [r for r in rows if r["verdict"] == "不合格"]
    pendings = [r for r in rows if r["verdict"] == "待确认"]
    if fails:
        head = fails[0]
        summary = (f"存在不合格项：{head['part']}在「{head['condition']}」超限"
                   f"（{head['stress_mpa']:g}MPa > {head['limit_mpa']:g}MPa）")
    elif pendings:
        summary = f"基本合格，存在 {len(pendings)} 项待确认（缺评价标准/安全系数）"
    elif rows:
        summary = "全部合格"
    else:
        summary = "（无判定数据）"
    return {"rows": rows, "judge_summary": summary, "fail_count": len(fails), "pending_count": len(pendings),
            "total": len(rows)}


# ---------------------------------------------------------------- 上下文派生（report.*）

def _fmt_mpa(v: float | None, digit: int = 1) -> str:
    return f"{v:.{digit}f}".rstrip("0").rstrip(".") if v is not None else "—"


def build_report_ctx(task: dict, parsed: dict, result: dict | None, standard: dict | None,
                     verdicts: dict) -> dict:
    task_name = task.get("task_name", "")
    task_type = parsed.get("task_type") or "结构强度"
    object_name = task.get("analysis_object", "")
    vehicle = task.get("vehicle_model", "")
    rows = verdicts["rows"]
    table = (result or {}).get("result_table") or []
    conditions = ((result or {}).get("conditions") or {}).get("all") or []
    images = (result or {}).get("image_manifest") or []
    std_name = (standard or {}).get("name", "企业标准")
    factors, _yields = _std_maps(standard)

    # 分析目的（三种情况：通用 / PDCA / 历史故障复核 —— 故障表 mock 阶段无数据，仅实现前两种）
    purpose = f"对{vehicle}{object_name}开展{task_type}，验证设计方案的强度可行性，为设计提供依据。"
    if parsed.get("pdca"):
        purpose = f"本任务为 PDCA 分析。{purpose}"

    # 分析方法
    factor_desc = "、".join(f"{c}×{factors[c]:g}" for c in factors) or "（未配置）"
    method = (f"强度分析采用许用应力法：许用应力＝材料屈服强度÷安全系数；标准工况系数依据《{std_name}》"
              f"（{factor_desc}），屈服强度取材料库数据；非标工况按工程师给定依据评价。")

    # 判定结论文本
    fails = [r for r in rows if r["verdict"] == "不合格"]
    pendings = [r for r in rows if r["verdict"] == "待确认"]
    lines = [f"共 {len(table)} 个部件、{len(rows)} 个工况点参与判定：{verdicts['judge_summary']}。"]
    for r in fails:
        lines.append(f"{r['part']}在「{r['condition']}」工况最大应力 {r['stress_mpa']:g}MPa，"
                     f"超过许用应力 {r['limit_mpa']:g}MPa（超限 {r['exceed_ratio']:g}%），"
                     f"建议复核该区域结构（如增加圆角/改用更高强度材料）。")
    if pendings:
        first = pendings[0]
        lines.append(f"另有 {len(pendings)} 项待确认（如 {first['part']}「{first['condition']}」"
                     f"缺评价标准与安全系数），需工程师补充依据后判定。")
    conclusion = "\n".join(lines)

    # 工况清单
    std_conds = [c for c in conditions if is_standard_condition(c)]
    nonstd_conds = [c for c in conditions if not is_standard_condition(c)]
    condition_items = [f"工况{i}：{c}" for i, c in enumerate(std_conds, start=1)]
    condition_items += [f"工况{i}：{c}（非标）" for i, c in enumerate(nonstd_conds, start=len(std_conds) + 1)]

    # 材料信息表：屈服强度优先二次处理表，其次标准持久化材料库；安全系数优先二次处理
    _, yields = _std_maps(standard)
    material_table = []
    for item in table:
        mat = item.get("material")
        y = item.get("yield_mpa") or (yields.get(mat or "") or {}).get("yield_mpa")
        f = item.get("safety_factor")
        material_table.append([item["part"], mat or "（待补充）",
                               _fmt_mpa(y) if y else "（待补充）",
                               f"{f:g}" if f else "按工况系数" if factors else "—"])

    # 表1：部位×工况 展平判定表
    stress_table = [[r["part"], r["condition"], f"{r['stress_mpa']:g}",
                     f"{r['limit_mpa']:g}" if r["limit_mpa"] is not None else "—", r["verdict"]] for r in rows]

    # 表2：非标工况
    nonstd_table = [[r["condition"], r["part"], f"{r['stress_mpa']:g}"]
                    for r in rows if not is_standard_condition(r["condition"])]

    # 图片分流（按文件名关键词）：
    #   含「载荷」→ 2.2 图2 载荷与边界条件；模型/model → 2.1 图1 分析模型；
    #   改善/方案 → 图4 改善方案（单列到第 4 章，避免与结果图重复）；
    #   其余图片（部件-工况 云图等）→ 第 3 章 图3 分析结果应力云图，全部按压缩包顺序填充
    def _caption(img: dict) -> str:
        if img.get("part") and img.get("condition"):
            return f"{img['part']}（{img['condition']}工况）"
        return Path(img["name"]).stem

    load_figures = [{"caption": _caption(i), "url": i["url"]}
                    for i in images if "载荷" in i["name"]]
    model_figures = [{"caption": _caption(i), "url": i["url"]} for i in images if i.get("is_model")]
    improve_figures = [{"caption": _caption(i), "url": i["url"]}
                       for i in images if any(k in i["name"] for k in ("改善", "方案", "improve"))]
    _claimed = {i["url"] for i in load_figures + model_figures + improve_figures}
    result_figures = [{"caption": _caption(i), "url": i["url"]}
                      for i in images if i["url"] not in _claimed]

    staff = task.get("authors") or {}
    return {
        "analysis_purpose": purpose,
        "analysis_method": method,
        "analysis_conclusion": conclusion,
        "conclusion_paragraphs": conclusion,
        "judge_summary": verdicts["judge_summary"],
        "condition_items": condition_items,
        "material_table": material_table,
        "stress_table": stress_table,
        "nonstd_table": nonstd_table,
        "load_figures": load_figures,
        "result_figures": result_figures,
        "model_figures": model_figures,
        "improve_figures": improve_figures,
        "improve_table": [],  # 改善方案数据需工程师后续提供，渲染为待补充
        "analysis_scope": f"{task_type}（{object_name}）",
        "software_and_time": f"分析软件：{task.get('analysis_software', '（待补充）')}\n分析时间：{task.get('date', '（待补充）')}",
        "staff_items": [f"分析人员（{role}）：{name}" for role, name in staff.items()] or ["（待补充）"],
    }


# ---------------------------------------------------------------- bind 解析

def _resolve(ctx: dict, path: str):
    node: Any = ctx
    for seg in path.split("."):
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            return False, None
    return True, node


# ---------------------------------------------------------------- DOCX 渲染

def _set_east_asia(target, east: str = "宋体", ascii_font: str = "Times New Roman"):
    """给样式或 run 设置中文字体（python-docx 需手动写 rFonts 的 eastAsia 属性）。"""
    rPr = target._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), east)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)


def _setup_styles(doc: Document):
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(10.5)
    _set_east_asia(normal, "宋体")
    for name, size, east in (("Title", 22, "黑体"), ("Heading 1", 16, "黑体"),
                             ("Heading 2", 14, "黑体"), ("Heading 3", 12, "黑体")):
        st = doc.styles[name]
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = BLACK
        _set_east_asia(st, east)


def _cell_bg(cell, hex_color: str = "D9D9D9"):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)


def _add_rich_text(paragraph, text: str, size: float | None = None, color=None, italic=False):
    """渲染文本，支持 **加粗** 记法与换行。"""
    for i, line in enumerate(str(text).split("\n")):
        if i:
            paragraph.add_run().add_break()
        for j, seg in enumerate(re.split(r"\*\*", line)):
            if not seg:
                continue
            run = paragraph.add_run(seg)
            run.bold = j % 2 == 1
            run.italic = italic
            if size:
                run.font.size = Pt(size)
            if color:
                run.font.color.rgb = color
            _set_east_asia(run)


def _add_caption(doc: Document, text: str, above: bool = True):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.font.size = Pt(9)
    run.bold = above
    run.font.color.rgb = BLACK
    _set_east_asia(run)


def _load_image_bytes(url: str) -> bytes | None:
    """图片 URL → bytes。本机 /files/... 直接读盘，远程走 httpx。"""
    try:
        parsed = urlparse(url)
        if parsed.path.startswith("/files/"):
            local = settings.data_root / unquote(parsed.path[len("/files/"):])
            if local.exists():
                return local.read_bytes()
        elif parsed.scheme in ("http", "https"):
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                return resp.content
    except Exception:  # noqa: BLE001 —— 图片失败降级为占位文本
        return None
    return None


def _render_info_table(doc: Document, rows: list[dict], ctx: dict, warnings: list[str]):
    table = doc.add_table(rows=0, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    pair: list[dict] = []

    def flush_pair():
        if not pair:
            return
        cells = table.add_row().cells
        for k, item in enumerate(pair):
            cells[k * 2].text = item["label"]
            _add_rich_text(cells[k * 2 + 1].paragraphs[0], str(item["value"]))
            _cell_bg(cells[k * 2], "F2F2F2")
        if len(pair) == 1:
            cells[2].merge(cells[3])
        pair.clear()

    for row in rows:
        if "bind" in row:
            found, value = _resolve(ctx, row["bind"])
            if not found or value in (None, ""):
                value, warn = "（待补充）", f"infoTable「{row['label']}」绑定 {row['bind']} 缺数据"
                if warn not in warnings:
                    warnings.append(warn)
            row = {**row, "value": value if value is not None else "（待补充）"}
        if row.get("half"):
            pair.append(row)
            if len(pair) == 2:
                flush_pair()
        else:
            flush_pair()
            cells = table.add_row().cells
            cells[0].text = row["label"]
            merged = cells[1].merge(cells[3])
            _add_rich_text(merged.paragraphs[0], str(row.get("value", "")))
            _cell_bg(cells[0], "F2F2F2")
    flush_pair()


def _render_data_table(doc: Document, block: dict, ctx: dict, warnings: list[str]):
    if block.get("caption") or block.get("label"):
        _add_caption(doc, f"{block.get('label', '')} {block.get('caption', '')}".strip())
    rows: list[list[str]] | None = []
    if block.get("bind"):
        found, value = _resolve(ctx, block["bind"])
        if not found:
            value, _ = None, warnings.append(f"table 绑定 {block['bind']} 缺数据")
        rows = value or []
        if not rows:
            warnings.append(f"表「{block.get('caption', block['bind'])}」无数据，渲染为待补充")
    columns = block.get("columns", [])
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, col in enumerate(columns):
        cell = table.rows[0].cells[i]
        cell.text = col
        _cell_bg(cell)
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in rows:
        cells = table.add_row().cells
        for i in range(len(columns)):
            v = str(r[i]) if i < len(r) else ""
            cells[i].text = v
    if not rows:
        p = doc.add_paragraph()
        run = p.add_run(f"（待补充：暂无数据，来源 {block.get('source', '—')}）")
        run.font.size = Pt(9)
        run.font.color.rgb = GRAY
        run.italic = True
        _set_east_asia(run)


def _render_figure(doc: Document, block: dict, ctx: dict, warnings: list[str]):
    figures: list[dict] = []
    if block.get("bind"):
        found, value = _resolve(ctx, block["bind"])
        if found:
            if isinstance(value, str):
                figures = [{"caption": block.get("caption", ""), "url": value}]
            else:
                figures = value or []
    if not figures:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"【{block.get('label', '')} {block.get('caption', '')}（图片待补充，来源 {block.get('source', '—')}）】")
        run.font.size = Pt(9)
        run.font.color.rgb = GRAY
        _set_east_asia(run)
        warnings.append(f"figure「{block.get('caption', block.get('bind'))}」无匹配图片")
        return
    for fig in figures:
        data = _load_image_bytes(fig.get("url", ""))
        caption = fig.get("caption") or block.get("caption", "")
        if data:
            try:
                import io

                doc.add_picture(io.BytesIO(data), width=Cm(13.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception:  # noqa: BLE001 —— 图片损坏降级为占位文本
                pass
        _add_caption(doc, f"{block.get('label', '')} {caption}".strip(), above=False)


def _render_block(doc: Document, block: dict, ctx: dict, warnings: list[str]):
    kind = block.get("kind")
    if kind == "paragraph":
        text = block.get("text")
        if block.get("bind"):
            found, value = _resolve(ctx, block["bind"])
            text = value if found and value not in (None, "") else "（待补充）"
            if not found:
                warnings.append(f"paragraph 绑定 {block['bind']} 缺数据")
        for line in str(text).split("\n"):
            p = doc.add_paragraph()
            _add_rich_text(p, line)
    elif kind == "list":
        items = block.get("items")
        if block.get("bind"):
            found, value = _resolve(ctx, block["bind"])
            items = value if found else []
            if not found or not items:
                warnings.append(f"list 绑定 {block['bind']} 缺数据")
        for item in items or []:
            p = doc.add_paragraph(style="List Bullet")
            _set_east_asia(p.add_run(str(item)))
    elif kind == "infoTable":
        _render_info_table(doc, block.get("rows", []), ctx, warnings)
    elif kind == "table":
        _render_data_table(doc, block, ctx, warnings)
    elif kind == "figure":
        _render_figure(doc, block, ctx, warnings)


def _render_section(doc: Document, section: dict, ctx: dict, warnings: list[str]):
    level = section["number"].count(".") + 1
    doc.add_heading(f"{section['number']} {section['title']}", level=min(level, 3))
    for block in section.get("blocks", []):
        _render_block(doc, block, ctx, warnings)
    if section.get("note") and "单独占一页" in section["note"]:
        doc.add_page_break()
    for child in section.get("children", []):
        _render_section(doc, child, ctx, warnings)


def render_doc(template: dict, ctx: dict, out_path: Path) -> list[str]:
    warnings: list[str] = []
    doc = Document()
    _setup_styles(doc)

    task = ctx["task"]
    title_text = f"{task.get('task_name', 'CAE 分析')}CAE 分析报告"
    title = doc.add_heading(title_text, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_rich_text(sub, f"{template['org']}　·　{template['doc_type']}　·　编号：{task.get('report_no', '—')}",
                   size=10, color=GRAY)

    # 签署表：编制/校对/审核/批准 ×（姓名、日期）
    sig = doc.add_table(rows=0, cols=3)
    sig.style = "Table Grid"
    sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    header = sig.add_row().cells
    for i, col in enumerate(("角色", "姓名", "日期")):
        header[i].text = col
        _cell_bg(header[i])
    authors = task.get("authors") or {}
    for s in template.get("signatures", []):
        cells = sig.add_row().cells
        cells[0].text = s["role"]
        cells[1].text = authors.get(s["role"], "（待补充）")
        cells[2].text = task.get("date", "（待补充）")
    doc.add_page_break()

    for section in template.get("sections", []):
        _render_section(doc, section, ctx, warnings)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("—— 本报告由 CAE 仿真报告智能体生成初版，待工程师确认后生效 ——")
    run.font.size = Pt(9)
    run.font.color.rgb = GRAY
    _set_east_asia(run)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return warnings


# ---------------------------------------------------------------- 接口

@router.post("/docx")
def generate_docx(req: DocGenRequest, request: Request):
    task = req.task
    task_name = task.get("task_name") or req.task_name or ""
    if not task_name:
        raise HTTPException(status_code=422, detail="缺少任务名称（task.task_name 或 task_name）")

    parsed = parse_task_type(task_name)
    template = None
    if req.template_id:
        template = find_template(req.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"模板不存在：{req.template_id}")
    else:
        template = find_template_by_task_type(parsed["task_type_code"])
        if not template:
            raise HTTPException(status_code=404,
                                detail=f"任务「{task_name}」解析为「{parsed['task_type'] or '未识别'}」，暂无对应模板")

    standard = req.standard or load_standard(parsed["task_type_code"])
    result = req.result or {}
    result_table = result.get("result_table") or []  # 允许空数据出稿（渲染为待补充，由 warnings 提示）

    verdicts = compute_verdicts(result_table, standard)
    report_ctx = build_report_ctx(task, parsed, result, standard, verdicts)
    ctx = {"task": task, "task_type_info": parsed, "report": report_ctx, "standard": standard or {}}

    safe_stem = re.sub(r'[\\/:*?"<>|\s]+', "_", req.file_name or f"{task_name}CAE分析报告")
    if not safe_stem.endswith(".docx"):
        safe_stem += ".docx"
    out_path = settings.exports_root / safe_stem
    warnings = render_doc(template, ctx, out_path)

    base_url = str(request.base_url).rstrip("/")
    return {
        "mock": True,
        "template_id": template["template_id"],
        "task_type_info": parsed,
        "file_name": out_path.name,
        "file_url": f"{base_url}/files/exports/{quote(out_path.name)}",
        "judge_summary": verdicts["judge_summary"],
        "verdicts": verdicts,
        "warnings": warnings,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
