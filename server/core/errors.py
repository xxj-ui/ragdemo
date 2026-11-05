"""统一错误码与异常（04 §3.3 / §3.5）

约定：
  - `code` 是稳定字符串，前端只按它分支；
  - `message` 是可直接展示的中文，不含堆栈/SQL/路径/Key；
  - HTTP 状态码仍表达类别，与 code 一起返回（信封 `{code,message,data}`）。
"""
from __future__ import annotations

from typing import Any

# code -> (HTTP 状态码, 默认中文文案)
ERROR_CODES: dict[str, tuple[int, str]] = {
    # 参数类
    "VALIDATION_ERROR": (422, "参数校验失败"),
    "QUESTION_EMPTY": (422, "问题不能为空"),
    "QUESTION_TOO_LONG": (422, "问题不能超过 500 字"),
    "TOO_MANY_FILES": (422, "文件数量超出上限，请分批提交"),
    "PAYLOAD_TOO_LARGE": (413, "请求体过大"),
    # 文件类（出现在 data.items[].error 内，不改变 HTTP 状态码）
    "UNSUPPORTED_FILE_TYPE": (400, "不支持的文件类型"),
    "FILE_TOO_LARGE": (400, "文件超过 50 MB"),
    "EMPTY_FILE": (400, "文件为空"),
    "INVALID_FILENAME": (400, "非法文件名"),
    "PARSE_FAILED": (400, "无法解析文件内容，可能是扫描件或空文档"),
    "TABLE_EMPTY": (400, "表格为空或无有效行"),
    "EMBEDDING_FAILED": (500, "向量化失败，请稍后重试"),
    "STORAGE_FAILED": (500, "文件保存失败"),
    # 资源类
    "DOCUMENT_NOT_FOUND": (404, "文档不存在"),
    "CONVERSATION_NOT_FOUND": (404, "会话不存在"),
    # 依赖类
    "DB_UNAVAILABLE": (503, "数据库不可用，请检查数据库服务"),
    "LLM_KEY_MISSING": (503, "未配置大模型 API Key"),
    "LLM_TIMEOUT": (504, "大模型响应超时，请重试"),
    "LLM_ERROR": (502, "大模型调用失败，请重试"),
    # 兜底
    "INTERNAL_ERROR": (500, "服务内部错误"),
    # 框架级（不在 04 §3.3 的业务错误码表里）：
    # NOT_FOUND = 未路由的路径/不存在的方法；NOT_IMPLEMENTED = 骨架期占位，实现后删除
    "NOT_FOUND": (404, "资源不存在"),
    "NOT_IMPLEMENTED": (501, "该接口尚未实现（框架骨架）"),
}


class AppError(Exception):
    """业务异常基类：携带可直接映射到响应的 code。"""

    def __init__(self, code: str, message: str | None = None) -> None:
        status, default_message = ERROR_CODES.get(code, (500, "服务内部错误"))
        self.code = code if code in ERROR_CODES else "INTERNAL_ERROR"
        self.http_status = status
        self.message = message or default_message
        super().__init__(self.message)


class ValidationFailure(AppError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(code, message)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(code, message)


class DependencyUnavailable(AppError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(code, message)


def error_body(code: str, message: str | None = None) -> dict[str, Any]:
    """统一失败信封。"""
    status, default_message = ERROR_CODES.get(code, (500, "服务内部错误"))
    return {"code": code, "message": message or default_message, "data": None}
