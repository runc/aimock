"""生成示例二次处理压缩包（理想格式），用于联调与冒烟测试。

内容（与 docs/cae仿真智能体需求整理.md 的理想格式示例表一致）：
- 二次处理结果表.csv：6 部件 × 9 工况（含 2 个非标工况）+ 评价标准
- 工况云图 png 若干：命名规范「部件-工况」（纯色占位图，非真实云图）

用法：uv run python scripts/make_sample_archive.py [输出路径]
默认输出 data/sample/TL2A车架强度分析_二次处理_理想格式.zip
"""

from __future__ import annotations

import struct
import sys
import zipfile
import zlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 部件, 材料, 标准工况×6（MPa）, 非标工况×2, 评价标准 —— 与需求整理理想格式表一致
IDEAL_ROWS = [
    ["部件 / 工况", "材料", "弯曲工况 bend", "扭转工况 torsion1", "转弯工况 Cornering",
     "扭转+转弯工况 tor+cor", "制动工况 brake", "双扭工况 bad",
     "吊点X向工况（非标）", "吊点Y向工况（非标）", "评价标准", "安全系数"],
    ["纵梁", "DL590", "118.3", "225.7", "130.5", "217.1", "191.1", "325.1", "241.7", "77.9", "<471MPa", ""],
    ["纵梁加强板", "DL591", "80.6", "158.2", "101.1", "146.5", "93.4", "231.8", "302.8", "66.2", "<326MPa", ""],
    ["外加强板", "DL592", "76.5", "151.9", "92.9", "173.2", "65.7", "200.8", "353.0", "105.9", "<326MPa", ""],
    ["第一横梁及支座", "DL593", "48.3", "128.4", "55.3", "122.5", "61.9", "180.0", "-", "-", "<297MPa", ""],
    ["第二横梁及支座", "DL594", "61.6", "127.6", "86.4", "119.2", "79.6", "172.1", "-", "-", "<231MPa", ""],
    ["第三横梁及连接板", "DL595", "24.0", "69.7", "39.1", "88.2", "22.5", "87.1", "-", "-", "<326MPa", ""],
]

# 每个部件最大应力工况配一张图（图3 用），另配载荷图/模型图/改善方案图
IMAGE_SPECS = [
    ("纵梁-双扭工况.png", (66, 133, 244)),
    ("纵梁加强板-扭转工况.png", (52, 168, 83)),
    ("外加强板-吊点X向工况.png", (234, 67, 53)),
    ("第一横梁及支座-扭转工况.png", (251, 188, 5)),
    ("载荷-弯曲工况.png", (255, 152, 0)),
    ("载荷-扭转+转弯工况.png", (121, 85, 72)),
    ("模型-有限元模型.png", (158, 158, 158)),
    ("改善方案-外加强板.png", (3, 218, 198)),
]


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """生成纯色 PNG（无第三方依赖的占位云图）。"""
    raw = b"".join(
        b"\x00" + bytes(rgb) * width for _ in range(height)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def build(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_text = "\n".join(",".join(row) for row in IDEAL_ROWS) + "\n"
        zf.writestr("二次处理结果表.csv", csv_text.encode("utf-8-sig"))
        for name, rgb in IMAGE_SPECS:
            zf.writestr(f"云图/{name}", make_png(320, 200, rgb))
    return out_path


def main() -> None:
    default = BASE_DIR / "data/sample/TL2A车架强度分析_二次处理_理想格式.zip"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    path = build(out)
    print(f"示例压缩包已生成：{path}（{path.stat().st_size / 1024:.1f} KB）")


if __name__ == "__main__":
    main()
