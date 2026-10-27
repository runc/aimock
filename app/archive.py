"""服务 b：二次处理数据压缩包解析与完整性/合法性校验（mock 可直接用于真实包）。

对应主流程第 3 步：chatbot 收 zip/rar 压缩包 → 工作流 HTTP 节点调本服务。

能力：
- zip（stdlib）与 rar（rarfile，依赖 unrar 工具，缺失时给出明确错误）解压；
  兼容 Windows 压缩的中文名（cp437→gbk 修正）。
- 识别数据表（csv/tsv/xlsx）与工况云图（png/jpg/jpeg/bmp，命名规范：部件-工况）。
- 兼容「理想格式」（部件+材料+各工况应力+评价标准/安全系数 单表）与
  「分开格式」（材料表 / 应力表 / 非标应力表 多表按部件合并）。
- 输出归一化 result_table：[{part, material, stresses{工况: MPa},
  eval_standard_mpa, safety_factor, yield_mpa}]，并给出 errors/warnings。

业务级校验失败（损坏/缺列/缺材料）返回 200 + valid=false，供 chatbot 直接展示；
请求本身问题（未传文件/类型不支持）返回 4xx。
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.requests import Request

from .config import settings
from .tasktype import STANDARD_CONDITIONS as STANDARD_CONDITION_NAMES
from .tasktype import is_standard_condition, normalize_condition

router = APIRouter(prefix="/api/archive", tags=["archive"])

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
TABLE_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".txt"}
# xls(97-2003) openpyxl 不支持，提示转换；txt 仅在内容像表时尝试

_NO_VALUE = {"", "-", "—", "–", "/", "\\", "无", "N/A", "n/a"}


def _norm_part(name: Any) -> str:
    return re.sub(r"[\s\u3000]+", "", str(name or ""))


def _parse_float(value: Any) -> float | None:
    """解析数值单元格：'-'/'' 返回 None（无数据），非数字抛 ValueError。"""
    text = str(value if value is not None else "").strip()
    if text in _NO_VALUE:
        return None
    return float(text.replace(",", "").replace("，", ""))


def _parse_eval_standard(value: Any) -> float | None:
    """解析评价标准：'<326MPa' / '≤326' / '326MPa' → 326.0。"""
    text = str(value if value is not None else "").strip()
    if text in _NO_VALUE:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _fix_zip_name(info: zipfile.ZipInfo) -> str:
    """修正 Windows 压缩包中文文件名（未设 UTF-8 标志位时 zipfile 按 cp437 解码）。"""
    try:
        return info.filename.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def _extract_package(package_path: Path, dest: Path, errors: list[dict]) -> bool:
    suffix = package_path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(package_path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    if info.flag_bits & 0x1:
                        errors.append({"code": "ENCRYPTED", "message": f"压缩包内文件已加密：{info.filename}"})
                        return False
                    target = dest / _fix_zip_name(info)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
        elif suffix == ".rar":
            import rarfile  # 延迟导入，未装 unrar 工具时错误更明确

            try:
                with rarfile.RarFile(str(package_path)) as rf:
                    rf.extractall(str(dest))
            except rarfile.Error as e:
                msg = str(e)
                if "unrar" in msg.lower() or "Unrar" in msg or "tool" in msg.lower():
                    errors.append({
                        "code": "RAR_TOOL_MISSING",
                        "message": "服务端缺少 unrar 工具，mock 阶段请上传 zip 格式压缩包",
                    })
                else:
                    errors.append({"code": "RAR_ERROR", "message": f"rar 解压失败：{msg}"})
                return False
        else:
            errors.append({"code": "UNSUPPORTED_TYPE", "message": f"不支持的压缩格式：{suffix}，请上传 zip/rar"})
            return False
        return True
    except zipfile.BadZipFile:
        errors.append({"code": "BAD_PACKAGE", "message": "压缩包损坏或不是有效的 zip 文件"})
        return False
    except Exception as e:  # noqa: BLE001 —— 解压环境问题统一回报给前端
        errors.append({"code": "EXTRACT_ERROR", "message": f"解压失败：{e}"})
        return False


# ---------------------------------------------------------------- 表格解析

def _decode_table_bytes(raw: bytes, file_name: str) -> tuple[str, str]:
    """返回 (文本, 编码)。csv/tsv/txt 依次尝试 utf-8-sig / gb18030。"""
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", errors="replace"), "gb18030(errors=replace)"


def _rows_from_csv(raw: bytes) -> list[list[Any]]:
    text, _ = _decode_table_bytes(raw, "")
    return [[cell for cell in row] for row in csv.reader(io.StringIO(text))] if text.strip() else []


def _rows_from_xlsx(path: Path) -> list[list[Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        return [list(row) for row in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def _cell_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


_PART_TOKENS = ("部件", "零件", "部位")
_EVAL_TOKENS = ("评价标准", "评判标准", "许用应力")
_FACTOR_TOKENS = ("安全系数",)
_YIELD_TOKENS = ("屈服",)
_EN_COND = ("bend", "torsion", "cornering", "brake", "bad", "tor+cor")


def _is_part_header(cell: str) -> bool:
    return any(t in cell for t in _PART_TOKENS)


def _is_condition_header(cell: str) -> bool:
    lowered = cell.lower()
    return "工况" in cell or any(t in lowered for t in _EN_COND)


def _classify_header_row(row: list[str]) -> dict | None:
    """识别表头行：返回 {part_idx, material_idx, yield_idx, eval_idx, factor_idx,
    condition_cols: [(idx, 规范工况名)], nonstd_flags}；不满足返回 None。"""
    part_idx = material_idx = yield_idx = eval_idx = factor_idx = None
    condition_cols: list[tuple[int, str]] = []
    for i, cell in enumerate(row):
        if _is_part_header(cell):
            part_idx = i
        elif "材料" in cell:
            material_idx = i
        elif any(t in cell for t in _YIELD_TOKENS):
            yield_idx = i
        elif any(t in cell for t in _EVAL_TOKENS):
            eval_idx = i
        elif any(t in cell for t in _FACTOR_TOKENS):
            factor_idx = i
        elif _is_condition_header(cell):
            condition_cols.append((i, normalize_condition(cell)))
    if part_idx is None or (material_idx is None and not condition_cols):
        return None
    return {
        "part_idx": part_idx,
        "material_idx": material_idx,
        "yield_idx": yield_idx,
        "eval_idx": eval_idx,
        "factor_idx": factor_idx,
        "condition_cols": condition_cols,
    }


def _detect_header(rows: list[list[Any]]) -> tuple[int, dict] | None:
    """在前 8 行内定位表头（二次处理表上方可能有标题行）。"""
    for idx, row in enumerate(rows[:8]):
        header = _classify_header_row([_cell_text(c) for c in row])
        if header:
            return idx, header
    return None


def _parse_table_file(path: Path, rel_name: str, errors: list[dict]) -> list[list[Any]] | None:
    try:
        if path.suffix.lower() in (".csv", ".tsv", ".txt"):
            return _rows_from_csv(path.read_bytes())
        if path.suffix.lower() == ".xlsx":
            return _rows_from_xlsx(path)
        return None
    except Exception as e:  # noqa: BLE001
        errors.append({"code": "TABLE_PARSE_ERROR", "message": f"表格 {rel_name} 解析失败：{e}"})
        return None


def _ingest_table(
    rows: list[list[Any]],
    rel_name: str,
    parts: dict[str, dict],
    tables_meta: list[dict],
    errors: list[dict],
    warnings: list[dict],
) -> None:
    """把一张二次处理表并入 parts（按部件聚合）。"""
    detected = _detect_header(rows)
    if not detected:
        errors.append({"code": "TABLE_HEADER_NOT_FOUND", "message": f"表格 {rel_name} 未找到表头（需包含 部件/零件 列）"})
        return
    header_row, header = detected
    h = header
    kind = (
        "material" if not h["condition_cols"]
        else "merged" if h["material_idx"] is not None
        else "stress"
    )
    data_count = 0
    for r, row in enumerate(rows[header_row + 1:], start=header_row + 2):
        cells = [_cell_text(c) for c in row]
        if not any(cells):
            continue
        part = _norm_part(cells[h["part_idx"]]) if h["part_idx"] < len(cells) else ""
        if not part or part in _NO_VALUE:
            continue
        entry = parts.setdefault(part, {"part": part, "material": None, "yield_mpa": None,
                                        "stresses": {}, "eval_raw": "", "eval_standard_mpa": None,
                                        "safety_factor": None, "_sources": set()})
        entry["_sources"].add(rel_name)
        if h["material_idx"] is not None and h["material_idx"] < len(cells):
            material = cells[h["material_idx"]] or None
            if material and entry["material"] and entry["material"] != material:
                warnings.append({"code": "MATERIAL_CONFLICT", "message": f"{rel_name} 第{r}行：部件 {part} 材料冲突（{entry['material']} → {material}）"})
            if material:
                entry["material"] = material
        if h["yield_idx"] is not None and h["yield_idx"] < len(cells):
            try:
                entry["yield_mpa"] = _parse_float(cells[h["yield_idx"]]) or entry["yield_mpa"]
            except ValueError:
                errors.append({"code": "BAD_NUMBER", "message": f"{rel_name} 第{r}行：屈服强度非数值 “{cells[h['yield_idx']]}”"})
        if h["eval_idx"] is not None and h["eval_idx"] < len(cells):
            raw = cells[h["eval_idx"]]
            if raw:
                entry["eval_raw"] = raw
                entry["eval_standard_mpa"] = _parse_eval_standard(raw)
        if h["factor_idx"] is not None and h["factor_idx"] < len(cells):
            try:
                entry["safety_factor"] = _parse_float(cells[h["factor_idx"]]) or entry["safety_factor"]
            except ValueError:
                errors.append({"code": "BAD_NUMBER", "message": f"{rel_name} 第{r}行：安全系数非数值 “{cells[h['factor_idx']]}”"})
        for col_idx, condition in h["condition_cols"]:
            if col_idx >= len(cells):
                continue
            raw = cells[col_idx]
            if raw in _NO_VALUE:
                entry["stresses"].setdefault(condition, None)
                continue
            try:
                entry["stresses"][condition] = _parse_float(raw)
            except ValueError:
                errors.append({"code": "BAD_NUMBER", "message": f"{rel_name} 第{r}行：{part} 「{condition}」应力非数值 “{raw}”"})
        data_count += 1
    tables_meta.append({
        "file": rel_name,
        "kind": kind,
        "rows": data_count,
        "conditions": [c for _, c in h["condition_cols"]],
    })


# ---------------------------------------------------------------- 图片解析

def _parse_image_stem(stem: str, known_parts: set[str], known_conditions: set[str]) -> tuple[str | None, str | None]:
    """'纵梁-弯曲工况' → (纵梁, 弯曲)；两侧都匹配不上已知部件/工况时返回 (None, None)，
    交由下游按文件名关键词（模型/改善方案等）识别。"""
    for sep in ("－", "—", "–", "-", "_"):
        if sep in stem:
            part_raw, cond_raw = stem.split(sep, 1)
            part = _norm_part(part_raw)
            cond = normalize_condition(cond_raw)
            # 部件名与表格部件宽松对齐（表格里可能是完整名如“第一横梁及支座”）
            matched = next((p for p in known_parts if p == part or p.startswith(part) or part.startswith(p)), None)
            cond_known = cond in known_conditions or cond in STANDARD_CONDITION_NAMES
            if matched is None and not cond_known:
                return None, None
            return matched, cond
    return None, None


def _is_model_image(stem: str) -> bool:
    return "模型" in stem or "model" in stem.lower() or "mesh" in stem.lower()


# ---------------------------------------------------------------- 主入口

@router.post("/parse")
async def parse_archive(
    request: Request,
    file: UploadFile = File(..., description="zip/rar 压缩包"),
    task_id: str | None = Query(None, description="可选：关联 SDM 任务，用于记录"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".zip", ".rar"):
        raise HTTPException(status_code=415, detail=f"仅支持 zip/rar 压缩包，收到：{suffix or '无扩展名'}")

    upload_id = uuid.uuid4().hex[:12]
    upload_dir = settings.uploads_root / upload_id
    extract_dir = upload_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    package_path = upload_dir / f"package{suffix}"
    package_path.write_bytes(await file.read())

    errors: list[dict] = []
    warnings: list[dict] = []
    tables_meta: list[dict] = []
    parts: dict[str, dict] = {}

    ok = _extract_package(package_path, extract_dir, errors)
    if ok:
        all_files = sorted(p for p in extract_dir.rglob("*") if p.is_file())
        if not all_files:
            errors.append({"code": "EMPTY_PACKAGE", "message": "压缩包为空"})
        table_files = [p for p in all_files if p.suffix.lower() in TABLE_EXTS]
        image_files = [p for p in all_files if p.suffix.lower() in IMAGE_EXTS]
        for p in all_files:
            ext = p.suffix.lower()
            rel = str(p.relative_to(extract_dir))
            if ext in (".xls",):
                warnings.append({"code": "UNSUPPORTED_TABLE", "message": f"{rel}：xls 暂不支持，请另存为 xlsx/csv"})
            elif ext not in TABLE_EXTS and ext not in IMAGE_EXTS:
                warnings.append({"code": "IGNORED_FILE", "message": f"{rel}：非表格/图片文件，已忽略"})

        for p in table_files:
            if p.suffix.lower() == ".xls":
                continue
            rows = _parse_table_file(p, str(p.relative_to(extract_dir)), errors)
            if rows:
                _ingest_table(rows, str(p.relative_to(extract_dir)), parts, tables_meta, errors, warnings)

    # 归一化部件行
    result_table: list[dict] = []
    for part, entry in parts.items():
        has_stress = any(v is not None for v in entry["stresses"].values())
        if not entry["material"]:
            errors.append({"code": "MATERIAL_MISSING", "message": f"部件 {part} 缺少材料信息（材料为必填）"})
        if not has_stress:
            errors.append({"code": "NO_STRESS", "message": f"部件 {part} 无任何工况应力数据"})
        if entry["eval_standard_mpa"] is None and entry["safety_factor"] is None:
            warnings.append({
                "code": "PENDING_CONFIRM",
                "message": f"部件 {part} 无评价标准且无安全系数，判定将进入「待确认」",
            })
        result_table.append({
            "part": part,
            "material": entry["material"],
            "yield_mpa": entry["yield_mpa"],
            "stresses": entry["stresses"],
            "eval_raw": entry["eval_raw"],
            "eval_standard_mpa": entry["eval_standard_mpa"],
            "safety_factor": entry["safety_factor"],
        })

    known_parts = set(parts.keys())
    known_conditions: set[str] = set()
    for entry in parts.values():
        known_conditions.update(entry["stresses"].keys())
    base_url = str(request.base_url).rstrip("/")
    image_manifest: list[dict] = []
    for p in sorted(extract_dir.rglob("*")) if ok else []:
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
            continue
        rel = str(p.relative_to(extract_dir))
        stem = Path(rel).stem
        part, condition = _parse_image_stem(stem, known_parts, known_conditions)
        image_manifest.append({
            "name": rel,
            "url": f"{base_url}/files/uploads/{upload_id}/extracted/{quote(rel)}",
            "part": part,
            "condition": condition,
            "is_model": _is_model_image(stem),
            "is_load": "载荷" in stem,  # 载荷/边界条件图 → 报告第 2 章
            "size_kb": round(p.stat().st_size / 1024, 1),
        })

    conditions: list[str] = []
    for entry in parts.values():
        for c in entry["stresses"]:
            if c not in conditions:
                conditions.append(c)
    nonstd_conditions = [c for c in conditions if not is_standard_condition(c)]

    valid = ok and not errors and bool(result_table)
    # 模型图/载荷图/改善方案图属于约定命名，不计入「未按规范命名」告警
    _special_kw = ("模型", "model", "mesh", "载荷", "改善", "方案", "improve")
    unmatched_images = [m["name"] for m in image_manifest
                        if not m["part"] and not m["is_model"]
                        and not any(k in m["name"].lower() for k in _special_kw)]
    if unmatched_images:
        warnings.append({
            "code": "IMAGE_UNMATCHED",
            "message": f"{len(unmatched_images)} 张图片无法按「部件-工况」解析命名：{'、'.join(unmatched_images[:5])}",
        })

    return {
        "mock": True,
        "upload_id": upload_id,
        "task_id": task_id,
        "file_name": file.filename,
        "valid": valid,
        "assumed_task_type": "结构强度",
        "tables": tables_meta,
        "result_table": result_table,
        "conditions": {"all": conditions, "standard": [c for c in conditions if is_standard_condition(c)],
                       "nonstandard": nonstd_conditions},
        "image_manifest": image_manifest,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "parts": len(result_table),
            "conditions": len(conditions),
            "images": len(image_manifest),
            "pending_confirm_parts": [
                r["part"] for r in result_table
                if r["eval_standard_mpa"] is None and r["safety_factor"] is None
            ],
        },
    }
