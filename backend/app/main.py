from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.endpoints import (
    accounts,
    agent_runs,
    analysis,
    assets,
    content,
    previews,
    publications,
    publish_tasks,
)
from backend.app.core.config import get_settings
from backend.app.db.session import close_db, init_db
from backend.app.schemas.system import HealthResponse


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Auto_Upt 后端 MVP：提供内容标准化、多平台草稿适配、预览持久化、"
        "模拟发布任务、公众号和 B站真实发布任务创建与查询能力。"
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "系统状态",
            "description": "用于确认后端服务是否正常启动的基础接口。",
        },
        {
            "name": "内容处理",
            "description": "内容标准化和即时多平台适配接口，不写入数据库。",
        },
        {
            "name": "预览管理",
            "description": "生成并查询多平台预览记录，数据会写入 PostgreSQL。",
        },
        {
            "name": "Agent 编排",
            "description": "第一阶段模拟多 Agent 内容分析、平台适配、校验和模拟发布流程。",
        },
        {
            "name": "发布任务",
            "description": "基于预览记录创建和查询模拟发布或真实发布任务。",
        },
        {
            "name": "素材管理",
            "description": "上传和管理公众号、B站真实发布所需的本地素材。",
        },
        {
            "name": "发布记录",
            "description": "查询、刷新或删除平台侧真实发布记录。",
        },
        {
            "name": "账号管理",
            "description": "连接和管理公众号、B站真实发布账号。",
        },
        {
            "name": "内容分析",
            "description": "深度内容分析：章节划分、媒体识别、多平台文案生成。",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content.router, prefix=settings.api_v1_prefix)
app.include_router(previews.router, prefix=settings.api_v1_prefix)
app.include_router(agent_runs.router, prefix=settings.api_v1_prefix)
app.include_router(assets.router, prefix=settings.api_v1_prefix)
app.include_router(publish_tasks.router, prefix=settings.api_v1_prefix)
app.include_router(publications.router, prefix=settings.api_v1_prefix)
app.include_router(accounts.router, prefix=settings.api_v1_prefix)
app.include_router(analysis.router, prefix=settings.api_v1_prefix)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["系统状态"],
    summary="健康检查",
    description=(
        "功能：检查后端服务是否已经正常启动。\n\n"
        "参数：无。\n\n"
        "返回值：返回服务状态、应用名称和当前运行环境。该接口不访问数据库，"
        "适合本地调试、容器探活和部署健康检查。"
    ),
    response_description="后端服务当前状态。",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
    )
