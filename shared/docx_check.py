"""docx 文件质量检查

提供单份 docx 的统计与异常检测。可用于转换后抽查、入库前校验等场景。

shared 层不预设阈值,所有阈值由调用方传入。
经验阈值(针对标准规范类文档)请见调用方,如 dev_tools 下的检查脚本。
"""
from pathlib import Path

from .word_parser import parse_docx


def check_docx(
    path,
    *,
    threshold_size_kb: float,
    threshold_block_count: int,
    threshold_text_chars: int,
    threshold_empty_ratio: float,
) -> dict:
    """检查单份 docx,返回统计字典。

    Args:
        path: docx 文件路径(str 或 Path)。
        threshold_size_kb: 文件大小下限(KB),小于此值触发"文件过小"警告。
        threshold_block_count: 总块数下限,小于此值触发"块数过少"警告。
        threshold_text_chars: 非空正文字符数下限,小于此值触发"正文过少"警告。
        threshold_empty_ratio: 空段占比上限,大于此值触发"空段占比过高"警告。

    Returns:
        统计字典,字段:
        - file_size_kb: 文件大小
        - block_count: 总块数(含段落/空段/表格/图片)
        - paragraph_count / empty_count / table_count / image_count: 各类计数
        - text_chars: 非空正文字符数(已去除 <含图片> 标记后再计)
        - empty_ratio: 空段占比(0.0 ~ 1.0)
        - warnings: 触发的警告列表,空表示无异常
        - parse_error: 解析失败时填错误信息,否则为空字符串
    """
    path = Path(path)
    file_size_kb = path.stat().st_size / 1024

    result = {
        "file_size_kb": round(file_size_kb, 1),
        "block_count": 0,
        "paragraph_count": 0,
        "empty_count": 0,
        "table_count": 0,
        "image_count": 0,
        "text_chars": 0,
        "empty_ratio": 0.0,
        "warnings": [],
        "parse_error": "",
    }

    try:
        blocks = parse_docx(str(path))
    except Exception as e:
        result["parse_error"] = f"{type(e).__name__}: {e}"
        result["warnings"].append("解析失败")
        return result

    result["block_count"] = len(blocks)
    for b in blocks:
        t = b["type"]
        if t == "paragraph":
            result["paragraph_count"] += 1
            # 字符数计算时去掉 <含图片> 标记的影响,避免该标记本身贡献字数
            text = b["text"].replace(" <含图片>", "").strip()
            result["text_chars"] += len(text)
        elif t == "empty":
            result["empty_count"] += 1
        elif t == "table":
            result["table_count"] += 1
        elif t == "image":
            result["image_count"] += 1

    if result["block_count"] > 0:
        result["empty_ratio"] = round(
            result["empty_count"] / result["block_count"], 3
        )

    if file_size_kb < threshold_size_kb:
        result["warnings"].append(f"文件过小(<{threshold_size_kb}KB)")
    if result["block_count"] < threshold_block_count:
        result["warnings"].append(f"块数过少(<{threshold_block_count})")
    if result["text_chars"] < threshold_text_chars:
        result["warnings"].append(f"正文过少(<{threshold_text_chars}字符)")
    if result["empty_ratio"] > threshold_empty_ratio:
        result["warnings"].append(
            f"空段占比过高(>{int(threshold_empty_ratio * 100)}%)"
        )

    return result
