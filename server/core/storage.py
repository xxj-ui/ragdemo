"""原文件存储（02 §4.2 支撑组件）

两种后端，由 `RAG_STORAGE_BACKEND` 选择：

  local（默认）  上传流 → data/uploads/<uuid>.<ext>，DB 存相对项目根的路径
  minio        上传流 → <spool>/.incoming-<uuid>.<ext>（解析需要本地文件）
               → put_object 到 s3://<bucket>/<prefix>/<uuid>.<ext>，DB 存完整的 s3:// 引用

两种后端共用同一套顺序约定（02 v0.4 / 03 §3.2）：
    临时文件 → 转正（local: os.replace / minio: put_object）→ 数据库事务 → 提交后删旧原文件
任一步失败 → 删掉刚落盘的正式文件或刚 put 的对象，旧数据与旧原文件保持原样（BR-2）。

对象存储没有 rename，但单对象 put 是原子的，所以「先就位、后替换」的语义不变，
只是补偿动作从 `unlink` 变成 `delete_object`。

`stored_path` 的两种取值由 `delete_ref()` 分派，兼容历史行（混存期不必写迁移脚本）：
    data/uploads/<uuid>.pdf            本地文件，相对项目根
    s3://zhiwen/documents/<uuid>.pdf  对象存储
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

from server.core.config import PROJECT_ROOT

logger = logging.getLogger("zhiwen.storage")

CHUNK = 1024 * 1024
S3_SCHEME = "s3://"

# 对象 Content-Type 按扩展名映射：不设的话 MinIO 只会记 binary/octet-stream，
# 将来做预签名下载/在线预览时浏览器会一律当附件下载。
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
}
DEFAULT_CONTENT_TYPE = "application/octet-stream"


class FileTooLarge(Exception):
    """流式写盘时超过上限。"""


class StorageError(Exception):
    """对象存储操作失败（配置缺失、连接失败、权限不足）。"""


def new_stored_path(upload_dir: Path, suffix: str) -> Path:
    """服务端生成的文件名：<uuid><ext>，与用户输入无关（AC-9）。"""
    return upload_dir / f"{uuid.uuid4().hex}{suffix.lower()}"


def new_spool_path(spool_dir: Path, suffix: str) -> Path:
    """上传中转文件：解析前先落本地，minio 后端 put 完成后即删。"""
    return spool_dir / f".incoming-{uuid.uuid4().hex}{suffix.lower()}"


def save_stream(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """流式写盘；超过 max_bytes 立即中断并删除半成品。返回写入字节数。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                block = src.read(CHUNK)
                if not block:
                    break
                written += len(block)
                if written > max_bytes:
                    raise FileTooLarge(str(written))
                out.write(block)
    except FileTooLarge:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return written


def promote(temp_path: Path, final_path: Path) -> None:
    """临时文件转正（同盘 rename，原子）。"""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, final_path)


def delete_quietly(path: Path) -> None:
    """删除本地文件；ENOENT 视为成功，其它异常只记日志（03 Q4 已确认）。"""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.error("删除原文件失败 path=%s err=%s", path, exc)


def sha256_of(path: Path) -> str:
    """分块算 sha256：写进对象元数据，用于「对象 ↔ 库」对账与完整性校验。"""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def is_object_ref(ref: str) -> bool:
    """`stored_path` 是对象引用（s3://bucket/key）还是本地相对路径。"""
    return (ref or "").startswith(S3_SCHEME)


def split_object_ref(ref: str) -> tuple[str, str]:
    """s3://bucket/key → (bucket, key)。"""
    rest = ref[len(S3_SCHEME):]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise StorageError(f"无法解析的对象引用：{ref}")
    return bucket, key


# ----------------------------------------------------------------------
# 后端实现：统一只暴露 publish() / delete_ref()
# ----------------------------------------------------------------------
class LocalStore:
    """写在项目目录 data/uploads/ 下（旧行为，保留给 RAG_STORAGE_BACKEND=local）。"""

    def __init__(self, upload_dir: Path) -> None:
        self.upload_dir = upload_dir

    def publish(self, temp: Path, suffix: str, filename: str | None = None) -> str:
        # filename 只有对象存储后端需要（写进对象元数据），本地后端不用
        final = new_stored_path(self.upload_dir, suffix)
        promote(temp, final)
        return final.relative_to(PROJECT_ROOT).as_posix()

    def delete_ref(self, ref: str) -> None:
        if is_object_ref(ref):
            logger.error("本地后端收到对象引用，跳过删除 ref=%s", ref)
            return
        delete_quietly(PROJECT_ROOT / ref)


class ObjectStore:
    """MinIO / S3 兼容对象存储（boto3，path-style 寻址）。"""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        prefix: str,
        region: str = "us-east-1",
    ) -> None:
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.prefix = prefix.strip("/")
        self.region = region
        self._client: Any = None

    # 客户端懒加载：只有真的走 minio 后端时才 import boto3 并建连接
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover
            raise StorageError("缺少对象存储依赖，请先安装 boto3") from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                # MinIO 走 127.0.0.1 / 容器名，必须 path-style，
                # 否则会解析成 <bucket>.<host> 这种不存在的主机名
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )
        return self._client

    def _key(self, suffix: str) -> str:
        name = f"{uuid.uuid4().hex}{suffix.lower()}"
        return f"{self.prefix}/{name}" if self.prefix else name

    def publish(self, temp: Path, suffix: str, filename: str | None = None) -> str:
        """把本地临时文件 put 成对象；成功后删临时文件，返回 s3:// 引用。

        对象上会带两样自证信息：
          - ContentType：按扩展名映射，供将来的预签名下载/预览直接使用
          - 用户元数据：sha256（完整性/对账）+ original-filename（脱离库也能认出身）
        注意 S3 用户元数据必须是 US-ASCII，中文文件名按 URL 编码写入，读时 unquote。
        """
        key = self._key(suffix)
        metadata = {"sha256": sha256_of(temp)}
        if filename:
            metadata["original-filename"] = quote(filename, safe="")
        try:
            with temp.open("rb") as fh:
                self.client().put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=fh,
                    ContentLength=temp.stat().st_size,
                    ContentType=CONTENT_TYPES.get(suffix.lower(), DEFAULT_CONTENT_TYPE),
                    Metadata=metadata,
                )
        except Exception as exc:  # botocore 异常种类很杂，统一收敛成 StorageError
            temp.unlink(missing_ok=True)
            raise StorageError(f"对象上传失败 key={key} err={exc}") from exc
        temp.unlink(missing_ok=True)
        return f"{S3_SCHEME}{self.bucket}/{key}"

    def delete_ref(self, ref: str) -> None:
        """删除对象；不存在视为成功，其它异常只记日志（与 delete_quietly 同口径）。"""
        if not is_object_ref(ref):
            # 混存期：minio 上线前写入的本地文件也按本地路径删掉
            delete_quietly(PROJECT_ROOT / ref)
            return
        try:
            bucket, key = split_object_ref(ref)
            self.client().delete_object(Bucket=bucket, Key=key)
        except Exception as exc:
            logger.error("删除对象失败 ref=%s err=%s", ref, exc)

    def exists(self, ref: str) -> bool:
        try:
            bucket, key = split_object_ref(ref)
            self.client().head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False


def build_store(settings: Any) -> LocalStore | ObjectStore:
    """按 `Settings.storage_backend` 装配存储后端（在容器里建一次，进程内复用）。"""
    backend = (settings.storage_backend or "local").lower()
    if backend == "minio":
        return ObjectStore(
            endpoint=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            prefix=settings.s3_prefix,
            region=settings.s3_region,
        )
    return LocalStore(settings.upload_dir)
