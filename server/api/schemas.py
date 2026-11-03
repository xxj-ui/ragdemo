"""请求/响应模型（04 §4 的逐字段落点）

字段名与 03 的列保持一致；唯一例外是上传结果的 `chunks`（SRS 7.1 已定名）。
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """04 §3.2：所有 JSON 响应同构三字段。"""

    code: str = "ok"
    message: str = "ok"
    data: T | None = None


class FileError(BaseModel):
    code: str
    message: str


class UploadItem(BaseModel):
    filename: str
    status: str = Field(description="success | failed")
    document_id: int | None = None
    chunks: int = 0
    overwritten: bool = False
    error: FileError | None = None


class UploadResult(BaseModel):
    items: list[UploadItem]


class DocumentItem(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    created_at: str
    updated_at: str


class DocumentList(BaseModel):
    items: list[DocumentItem]


class DocumentBrief(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    updated_at: str


class DocumentChunkItem(BaseModel):
    chunk_id: int
    chunk_index: int
    page: str | None = None
    content: str


class DocumentChunks(BaseModel):
    """文档只读预览（FR-8）：按 chunk_index 顺序分页。"""

    document: DocumentBrief
    total: int
    offset: int
    limit: int
    items: list[DocumentChunkItem]


class ChatRequest(BaseModel):
    question: str


class CitationItem(BaseModel):
    n: int
    filename: str
    page: str | None = None
    snippet: str
    chunk_id: int


class MessageItem(BaseModel):
    role: str = Field(description="user | assistant")
    content: str
    citations: list[CitationItem] = []


class ConversationListItem(BaseModel):
    id: int
    title: str
    created_at: str


class ConversationList(BaseModel):
    items: list[ConversationListItem]


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: str
    messages: list[MessageItem]


class HealthData(BaseModel):
    status: str = Field(description="ok | degraded")
    database: str = Field(description="ok | error")
    embedding_model: str = Field(description="loaded | loading | failed")
    llm_key: str = Field(description="configured | missing")
