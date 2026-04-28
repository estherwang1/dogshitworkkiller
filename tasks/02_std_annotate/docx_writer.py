"""把节边界标记插回 docx。

按 word_parser.parse_docx 的遍历顺序映射段落编号到实际段落对象,
在每个目标段落前插入一个新段落作为分块标识符。

任务 02 专属模块,不进 shared(标识符插入是标注任务独有需求)。
"""
import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

# XML 命名空间常量,和 word_parser 保持一致
W_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TAG_PARAGRAPH = f"{{{W_NAMESPACE}}}p"
TAG_TABLE = f"{{{W_NAMESPACE}}}tbl"


def insert_section_markers(
    input_path,
    output_path,
    blocks: list[dict],
    markers: list[dict],
    *,
    marker_text: str = "<<<SECTION>>>",
) -> int:
    """在 docx 的指定段落前插入分块标识符。

    实现细节:
    - 遍历顺序与 word_parser.parse_docx 完全一致,保证段落编号对得上
    - 新段落用 Normal 样式,不继承目标段落的样式(避免标识符被识别成标题)
    - 没有要插的 marker 时直接复制源文件,保持输出存在

    Args:
        input_path: 原 docx 路径(str 或 Path)。
        output_path: 输出 docx 路径(str 或 Path)。
        blocks: word_parser.parse_docx 的输出,用于编号映射。
        markers: 节标记列表,每项含"段落编号"字段。
        marker_text: 插入的标识符文本,默认 "<<<SECTION>>>"。

    Returns:
        实际插入的标记数。
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    marker_ids = {m.get("段落编号", "") for m in markers if m.get("段落编号")}

    if not marker_ids:
        shutil.copy(str(input_path), str(output_path))
        return 0

    doc = Document(str(input_path))
    body = doc.element.body
    paragraph_map = {p._element: p for p in doc.paragraphs}

    # 第一遍:按 word_parser 同样的顺序遍历,定位 marker_ids 对应的段落对象
    targets = []
    index = 0
    for child in body.iterchildren():
        if child.tag == TAG_PARAGRAPH:
            paragraph = paragraph_map.get(child)
            if paragraph is None:
                continue
            index += 1
            pid = f"P{index:04d}"
            if pid in marker_ids:
                targets.append(paragraph)
        elif child.tag == TAG_TABLE:
            index += 1
            # 表格不会被标为节边界(标注 prompt 已要求),略过

    # 第二遍:在每个目标段落前插入 marker 段落,强制 Normal 样式
    inserted = 0
    try:
        normal_style = doc.styles["Normal"]
    except KeyError:
        normal_style = None

    for target in targets:
        new_para = target.insert_paragraph_before(marker_text)
        if normal_style is not None:
            new_para.style = normal_style
        inserted += 1

    doc.save(str(output_path))
    return inserted
