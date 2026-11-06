"""RAG Demo —— 第 1 步：文档加载

统一把不同格式的文档读成：

    [
        {"text": "...", "source": "文件.pdf", "page": 3},
        ...
    ]

每个元素代表"一页 / 一段 / 一行"，后续切分只在单个元素内部进行，
不会跨页拼接，保证 chunk 的页码来源是准确的。

支持的格式：txt / md / pdf / docx / xlsx / csv
"""

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("ragdemo.loaders")

# ------------------------------------------------------------------
# 扫描件 OCR：RapidOCR（PP-OCRv4，纯 CPU，模型随 wheel 内置）
#   引擎是进程级单例（初始化约 0.6 s），只有真的遇到「无文字层」的页才加载
# ------------------------------------------------------------------
_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr_engine():
    """懒加载 OCR 引擎；放在函数里 import，避免没装依赖时整个解析模块不可用。"""
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                from rapidocr_onnxruntime import RapidOCR

                # 关方向分类（扫描件基本都是正向）、8 线程：实测 1.1~2.9 s/页、相似度 0.99
                _ocr_engine = RapidOCR(use_cls=False, intra_op_num_threads=8)
    return _ocr_engine


def _ocr_page(pdfium_doc, page_no: int, dpi: int, name: str) -> str:
    """把第 page_no 页渲染成图再识别；失败返回空串（不阻断整篇导入）。"""
    import numpy as np

    started = time.perf_counter()
    try:
        pil = pdfium_doc[page_no - 1].render(scale=dpi / 72).to_pil()
        result, _ = _get_ocr_engine()(np.array(pil))
        text = "".join(item[1] for item in (result or [])).strip()
    except Exception as exc:                      # 单页 OCR 失败不该让整份文件失败
        logger.warning("OCR 失败 %s 第 %d 页：%s: %s", name, page_no, type(exc).__name__, exc)
        return ""
    logger.info("OCR %s 第 %d 页：%d 字，%.2f s", name, page_no, len(text), time.perf_counter() - started)
    return text


# ------------------------------------------------------------------
# 各类型的 loader：只负责"把文件内容变成文本"
# ------------------------------------------------------------------


def _read_text_file(path: Path) -> str:
    """统一按 UTF-8 读取，utf-8-sig 会自动去掉文件开头的 BOM。

    注意：GBK 编码的老文件会被读成乱码（不报错）。
    如果发现某份 txt / csv 满屏乱码，再针对它单独处理。
    """
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load_txt(path: Path) -> list[dict]:
    text = _read_text_file(path).strip()
    if not text:
        return []
    return [{"text": text, "source": path.name, "page": None}]


def load_pdf(
    path: Path,
    *,
    ocr: bool = True,
    ocr_dpi: int = 120,
    ocr_min_chars: int = 10,
    ocr_max_pages: int = 0,
) -> list[dict]:
    """按页提取；某页几乎没有文字（扫描件）时按需走 OCR。

    OCR 只在「该页抽到的字符 < ocr_min_chars」时触发：
      * 渲染：pypdfium2（120 dpi，实测约 50 ms/页）
      * 识别：RapidOCR（PP-OCRv4，本机 CPU 首屏 2.9 s（含引擎加载）、之后 1.1~1.6 s/页，字符相似度 0.99）
    `ocr_max_pages > 0` 时最多 OCR 这么多页，避免超长扫描件把导入拖死；
    `ocr=False` 时行为与旧版一致（跳过并告警）。
    """
    import pdfplumber  # 延迟导入：只有加载 PDF 时才需要这个库

    docs: list[dict] = []
    pdfium_doc = None
    ocr_pages = 0
    try:
        with pdfplumber.open(path) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                if len(text) < ocr_min_chars:
                    if not ocr:
                        logger.warning("%s 第 %d 页几乎没有文字（疑似扫描件），OCR 已关闭，跳过", path.name, page_no)
                        continue
                    if ocr_max_pages and ocr_pages >= ocr_max_pages:
                        logger.warning("%s 第 %d 页需要 OCR，但已达上限 %d 页，跳过", path.name, page_no, ocr_max_pages)
                        continue
                    if pdfium_doc is None:
                        import pypdfium2

                        pdfium_doc = pypdfium2.PdfDocument(str(path))
                    text = _ocr_page(pdfium_doc, page_no, ocr_dpi, path.name)
                    ocr_pages += 1
                if not text:
                    continue
                docs.append({"text": text, "source": path.name, "page": page_no})
    finally:
        if pdfium_doc is not None:
            pdfium_doc.close()
    if ocr_pages:
        logger.info("%s 共 OCR %d 页", path.name, ocr_pages)
    return docs


def load_docx(path: Path) -> list[dict]:
    """段落 + 表格都提取。表格单独转成 "单元格 | 单元格" 的行。"""
    from docx import Document

    doc = Document(path)
    parts = []

    for p in doc.paragraphs:
        line = p.text.strip()
        if line:
            parts.append(line)

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            line = " | ".join(c for c in cells if c)
            if line:
                parts.append(line)

    text = "\n".join(parts).strip()
    if not text:
        return []
    return [{"text": text, "source": path.name, "page": None}]


def _rows_to_docs(rows: list[list], source: str, sheet: str) -> list[dict]:
    """把表格的每一行转成 "列名: 值, 列名: 值" 的文本。

    每一行都重复表头 —— 这是表格能被检索到的关键，
    否则单独的 "1200" 对模型来说没有任何含义。
    """
    if not rows:
        return []

    raw_header = rows[0]
    header = [
        str(c).strip() if c is not None and str(c).strip() else f"列{i + 1}"
        for i, c in enumerate(raw_header)
    ]

    docs = []
    for row_no, row in enumerate(rows[1:], start=2):  # 行号按 Excel 习惯从 1 开始，+1 是表头
        cells = [str(c).strip() if c is not None else "" for c in row]
        if not any(cells):
            continue
        pairs = [
            f"{header[i]}: {cells[i]}"
            for i in range(min(len(header), len(cells)))
            if cells[i]
        ]
        if not pairs:
            continue
        docs.append({
            "text": ", ".join(pairs),
            "source": source,
            "page": f"{sheet}!{row_no}",   # 例如 "Q3!12"：第 12 行
        })
    return docs


def load_excel(path: Path) -> list[dict]:
    """xlsx 按 sheet 遍历；csv 用标准库读取，两者共用行转文本逻辑。"""
    if path.suffix.lower() == ".csv":
        import csv

        with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            rows = [list(r) for r in csv.reader(f)]
        return _rows_to_docs(rows, path.name, sheet="csv")

    from openpyxl import load_workbook

    docs = []
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            docs.extend(_rows_to_docs(rows, path.name, sheet=ws.title))
    finally:
        wb.close()
    return docs


# ------------------------------------------------------------------
# 分发入口
# ------------------------------------------------------------------

LOADERS = {
    ".txt": load_txt,
    ".md": load_txt,
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".xlsx": load_excel,
    ".xlsm": load_excel,
    ".csv": load_excel,
}


def load(path: str | Path, **kwargs) -> list[dict]:
    """加载单个文件。不支持的类型直接抛错，避免悄悄漏数据。

    `**kwargs` 只对 PDF 有意义（OCR 开关/DPI/页数上限），其它格式忽略。
    """
    path = Path(path)
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"不支持的文件类型: {path.suffix}（{path.name}）")
    if loader is load_pdf:
        return loader(path, **kwargs)
    return loader(path)


def load_all(input_path: str | Path) -> list[dict]:
    """文件或目录（递归）。单个文件失败不影响其它文件。"""
    p = Path(input_path)
    if p.is_file():
        return load(p)
    if not p.is_dir():
        raise FileNotFoundError(f"路径不存在: {p}")

    docs, failed = [], []
    for f in sorted(p.rglob("*")):
        if f.is_file() and f.suffix.lower() in LOADERS:
            try:
                docs.extend(load(f))
            except Exception as e:
                failed.append((f.name, e))

    if failed:
        print("\n以下文件加载失败：")
        for name, err in failed:
            print(f"  - {name}: {err}")
    return docs
