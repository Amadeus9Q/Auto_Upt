from typing import Annotated

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from backend.app.adapters.registry import default_platforms
from backend.app.schemas.content import (
    AdaptContentRequest,
    AdaptContentResponse,
    ContentInput,
    ImportDocumentResponse,
    NormalizeResponse,
    PlatformListResponse,
)
from backend.app.services.import_service import ImportService
from backend.app.services.preview_service import PreviewService


router = APIRouter(prefix="/content", tags=["内容处理"])


@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    summary="标准化内容",
    description=(
        "功能：将用户输入的原始内容转换为后端统一内容 IR，供后续平台适配和预览生成使用。\n\n"
        "参数：请求体包含标题、正文、内容类型、标签和素材列表。其中正文为必填；"
        "标题为空时会从正文首个非空行推断；标签会去重并去掉前缀 `#`。\n\n"
        "返回值：返回 `content_ir`，包含标题、正文、摘要、内容类型、标准化标签、"
        "素材、字数和创建时间等信息。该接口不写入数据库。"
    ),
    response_description="标准化后的统一内容 IR。",
)
async def normalize_content(
    request: Annotated[
        ContentInput,
        Body(description="原始内容输入，正文 `body` 为必填字段。"),
    ],
) -> NormalizeResponse:
    service = PreviewService()
    return NormalizeResponse(content_ir=service.normalize_content(request))


@router.post(
    "/adapt",
    response_model=AdaptContentResponse,
    summary="生成多平台草稿",
    description=(
        "功能：在不落库的情况下，将原始内容标准化并渲染成公众号、知乎、小红书、B站等平台草稿。\n\n"
        "参数：请求体包含内容输入字段和可选的 `platforms` 平台列表。"
        "`platforms` 为空时默认适配当前后端支持的全部平台。\n\n"
        "返回值：返回统一内容 IR、按平台分组的草稿 `drafts`，以及按平台分组的"
        "格式校验报告 `validation_report`。如果传入不支持的平台，返回 400。"
    ),
    response_description="多平台草稿和格式校验报告。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def adapt_content(
    request: Annotated[
        AdaptContentRequest,
        Body(description="需要适配的平台和原始内容输入。"),
    ],
) -> AdaptContentResponse:
    service = PreviewService()
    try:
        content_ir, drafts, validation_report = service.adapt_content(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AdaptContentResponse(
        content_ir=content_ir,
        drafts=drafts,
        validation_report=validation_report,
    )


@router.get(
    "/platforms",
    response_model=PlatformListResponse,
    summary="查询支持的平台",
    description=(
        "功能：查询当前后端已经注册的平台适配器。\n\n"
        "参数：无。\n\n"
        "返回值：返回平台标识列表。当前 MVP 支持 `wechat`、`zhihu`、"
        "`xiaohongshu` 和 `bilibili`。"
    ),
    response_description="当前后端支持的平台列表。",
)
async def list_platforms() -> PlatformListResponse:
    return PlatformListResponse(platforms=default_platforms())


@router.post(
    "/import",
    response_model=ImportDocumentResponse,
    summary="导入文档并提取结构化内容",
    description=(
        "功能：上传 .md、.txt 或 .docx 文件，后端解析后调用 LLM 提取标题、正文、标签、"
        "摘要、内容类型及媒体资源位置。\n\n"
        "支持格式：Markdown（.md）、纯文本（.txt）、Word（.docx）。\n\n"
        "返回值：可直接用于填充前端编辑器的结构化内容，包含：\n"
        "- title：提取的标题\n"
        "- body：完整正文（Markdown 纯文本）\n"
        "- tags：自动生成的中文标签列表\n"
        "- summary：100-200 字摘要\n"
        "- content_type：推断的内容类型（article/video/mixed）\n"
        "- media：文档中的媒体资源列表（含位置、类型、描述）\n"
        "- raw_text：原始纯文本，供兜底使用"
    ),
    response_description="从文档提取的结构化内容。",
    responses={
        400: {"description": "不支持的文件格式或文件损坏。"},
    },
)
async def import_document(
    file: Annotated[
        UploadFile,
        File(description="待导入的文档文件（.md 或 .docx）。"),
    ],
) -> ImportDocumentResponse:
    filename = (file.filename or "").lower()
    if not (filename.endswith(".md") or filename.endswith(".markdown") or filename.endswith(".docx") or filename.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式：{file.filename}。请上传 .md、.txt 或 .docx 文件。",
        )
    service = ImportService()
    return await service.import_document(file)
