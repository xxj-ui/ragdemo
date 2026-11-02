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

from pathlib import Path

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


def load_pdf(path: Path) -> list[dict]:
    """按页提取。没有文字层的页大概率是扫描件，先跳过并给出警告。"""
    import pdfplumber  # 延迟导入：只有加载 PDF 时才需要这个库

    docs = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if len(text) < 10:
                print(f"  [警告] {path.name} 第 {page_no} 页几乎没有文字，可能是扫描件（暂不做 OCR）")
                continue
            docs.append({"text": text, "source": path.name, "page": page_no})
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


def load(path: str | Path) -> list[dict]:
    """加载单个文件。不支持的类型直接抛错，避免悄悄漏数据。"""
    path = Path(path)
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"不支持的文件类型: {path.suffix}（{path.name}）")
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
