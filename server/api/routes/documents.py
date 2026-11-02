"""M1 文档管理路由：04 §4.1~§4.3"""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from server.api.deps import get_container
from server.core.errors import AppError
from server.api.schemas import DocumentList, Envelope, UploadItem, UploadResult
from server.services import documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=Envelope[UploadResult], summary="上传文档（每次 1 个）")
async def upload_document(files: list[UploadFile] = File(..., description="长度为 1 的文件数组")):
    if len(files) != 1:
        raise AppError("TOO_MANY_FILES")
    result = await documents.upload(get_container(), files[0])
    # 每次请求只处理 1 个文件，但仍然按 04 的 items[] 结构返回（前端逐行渲染）
    return Envelope(data=UploadResult(items=[UploadItem(**result)]))


@router.get("", response_model=Envelope[DocumentList], summary="文档列表（全量，不分页）")
async def list_documents():
    result = documents.list_documents(get_container())
    return Envelope(data=DocumentList(**result))


@router.delete("/{document_id}", response_model=Envelope[None], summary="删除文档")
async def delete_document(document_id: int):
    documents.delete_document(get_container(), document_id)
    return Envelope(data=None)
