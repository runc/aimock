"""server-v2 入口：mock 服务集（无数据库，文件即存储）。

四个主服务（docs/cae智能体与工作流设计.md 需求 1）：
  a. /api/sdm/*        SDM 仿真任务基本信息
  b. /api/archive/*    二次处理压缩包解析与校验
  c. /api/report/docx  Word 文档生成
  d. /api/templates/*  模板结构化信息
辅助：/api/standards/* 标准二维表按任务类型持久化（主流程第 5 条）
静态：/files/**         上传文件与导出 docx 的下载
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import archive, docgen, sdm, standards, templates
from .config import ensure_dirs, settings

app = FastAPI(
    title="CAE 仿真报告智能体 server-v2（mock 服务集）",
    version="0.1.0",
    description="SDM 任务信息 / 压缩包解析校验 / Word 生成 / 模板结构化信息 / 标准持久化",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sdm.router)
app.include_router(archive.router)
app.include_router(templates.router)
app.include_router(standards.router)
app.include_router(docgen.router)


@app.on_event("startup")
def startup() -> None:
    ensure_dirs()
    standards.seed_if_missing()


@app.get("/api/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "service": "server-v2",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# 上传文件与导出文件的静态下载（/files/uploads/**、/files/exports/**）
ensure_dirs()
app.mount("/files", StaticFiles(directory=str(settings.data_root)), name="files")
