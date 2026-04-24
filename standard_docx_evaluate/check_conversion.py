"""
转换质量自动检查脚本

用途:pdf_to_docx.py 跑完后,扫描输出目录的每份 docx,
统计关键指标,列出可能转换失败的文件供人工复核。

检查信号:
- 文件大小过小
- 总块数过少
- 非空正文字符数过少
- 空段占比过高

输出:
- 控制台打印统计汇总
- convert_check.json 详细数据,一份文件一条
- 异常清单单独打印出来

依赖:
    word_parser.py (同目录)
    python-docx

用法:
    改下方配置区,运行。
"""
import os
import sys
import json
from datetime import datetime

from word_parser import parse_docx

sys.stdout.reconfigure(line_buffering=True)

# ============= 配置区 =============
CONVERTED_DIR = r"C:\std_gov\converted_docx"
CHECK_REPORT  = r"C:\std_gov\convert_check.json"

# 异常阈值(经验值,可根据实际数据调整)
THRESHOLD_FILE_SIZE_KB   = 5       # 文件大小 < 此值 → 疑似失败
THRESHOLD_BLOCK_COUNT    = 20      # 总块数 < 此值 → 疑似失败
THRESHOLD_TEXT_CHARS     = 500     # 非空正文字符数 < 此值 → 疑似失败
THRESHOLD_EMPTY_RATIO    = 0.70    # 空段占比 > 此值 → 疑似失败
# ==================================


def check_docx(path: str) -> dict:
    """检查单份 docx,返回统计字典"""
    file_size_kb = os.path.getsize(path) / 1024

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
        blocks = parse_docx(path)
    except Exception as e:
        result["parse_error"] = f"{type(e).__name__}: {e}"
        result["warnings"].append("解析失败")
        return result

    result["block_count"] = len(blocks)
    for b in blocks:
        t = b["type"]
        if t == "paragraph":
            result["paragraph_count"] += 1
            # 计文字字符数(去掉 <含图片> 这种标记的影响)
            text = b["text"].replace(" <含图片>", "").strip()
            result["text_chars"] += len(text)
        elif t == "empty":
            result["empty_count"] += 1
        elif t == "table":
            result["table_count"] += 1
        elif t == "image":
            result["image_count"] += 1

    if result["block_count"] > 0:
        result["empty_ratio"] = round(result["empty_count"] / result["block_count"], 3)

    # 触发异常规则
    if file_size_kb < THRESHOLD_FILE_SIZE_KB:
        result["warnings"].append(f"文件过小(<{THRESHOLD_FILE_SIZE_KB}KB)")
    if result["block_count"] < THRESHOLD_BLOCK_COUNT:
        result["warnings"].append(f"块数过少(<{THRESHOLD_BLOCK_COUNT})")
    if result["text_chars"] < THRESHOLD_TEXT_CHARS:
        result["warnings"].append(f"正文过少(<{THRESHOLD_TEXT_CHARS}字符)")
    if result["empty_ratio"] > THRESHOLD_EMPTY_RATIO:
        result["warnings"].append(f"空段占比过高(>{int(THRESHOLD_EMPTY_RATIO*100)}%)")

    return result


def batch_check():
    if not os.path.isdir(CONVERTED_DIR):
        print(f"未找到目录: {CONVERTED_DIR}")
        return

    docx_files = []
    for root, _dirs, filenames in os.walk(CONVERTED_DIR):
        for fname in filenames:
            if fname.lower().endswith(".docx") and not fname.startswith("~$"):
                docx_files.append(os.path.join(root, fname))
    docx_files.sort()

    if not docx_files:
        print(f"{CONVERTED_DIR} 下没有 .docx 文件")
        return

    print(f"开始检查 {len(docx_files)} 份文件...\n")

    report = []
    abnormal_count = 0
    for idx, path in enumerate(docx_files, 1):
        rel = os.path.relpath(path, CONVERTED_DIR)
        stat = check_docx(path)
        entry = {"file": rel, **stat}
        report.append(entry)
        if stat["warnings"] or stat["parse_error"]:
            abnormal_count += 1
        # 进度打印
        if idx % 10 == 0 or idx == len(docx_files):
            print(f"  已检查 {idx}/{len(docx_files)}")

    # 保存完整报告
    os.makedirs(os.path.dirname(CHECK_REPORT) or ".", exist_ok=True)
    out = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "directory": CONVERTED_DIR,
        "total": len(docx_files),
        "abnormal": abnormal_count,
        "thresholds": {
            "file_size_kb": THRESHOLD_FILE_SIZE_KB,
            "block_count": THRESHOLD_BLOCK_COUNT,
            "text_chars": THRESHOLD_TEXT_CHARS,
            "empty_ratio": THRESHOLD_EMPTY_RATIO,
        },
        "files": report,
    }
    with open(CHECK_REPORT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n=== 检查结果 ===")
    print(f"总文件数: {len(docx_files)}")
    print(f"异常文件数: {abnormal_count}")
    print(f"详细报告: {CHECK_REPORT}")

    # 统计汇总(供感知分布情况)
    if report:
        sizes = [e["file_size_kb"] for e in report if not e["parse_error"]]
        blocks = [e["block_count"] for e in report if not e["parse_error"]]
        chars = [e["text_chars"] for e in report if not e["parse_error"]]
        empty_ratios = [e["empty_ratio"] for e in report if not e["parse_error"]]

        def mm(lst):
            if not lst:
                return "-"
            return f"min={min(lst)}, max={max(lst)}, 中位={sorted(lst)[len(lst)//2]}"

        print(f"\n=== 指标分布(供阈值参考) ===")
        print(f"  文件大小(KB): {mm(sizes)}")
        print(f"  块数: {mm(blocks)}")
        print(f"  正文字符数: {mm(chars)}")
        print(f"  空段比例: {mm([round(r,2) for r in empty_ratios])}")

    if abnormal_count == 0:
        print("\n所有文件通过检查")
        return

    print(f"\n=== 异常文件清单 ===")
    for entry in report:
        if entry["warnings"] or entry["parse_error"]:
            reasons = ", ".join(entry["warnings"])
            if entry["parse_error"]:
                reasons = f"{reasons}; 解析错误: {entry['parse_error']}" if reasons else f"解析错误: {entry['parse_error']}"
            print(f"  [{reasons}]")
            print(f"    文件: {entry['file']}")
            print(f"    大小={entry['file_size_kb']}KB, 块数={entry['block_count']}, "
                  f"正文字符={entry['text_chars']}, 空段比例={entry['empty_ratio']}")


if __name__ == "__main__":
    batch_check()
