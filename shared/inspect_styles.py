"""
辅助工具:扫描一份 word 文档,列出所有出现过的段落 style 名字及其次数

用法: python inspect_styles.py 某标准.docx
"""
import sys
from collections import Counter
from word_parser import parse_docx


def main(path: str):
    blocks = parse_docx(path)
    style_counter = Counter()
    type_counter = Counter()

    for block in blocks:
        type_counter[block["type"]] += 1
        if block["type"] == "paragraph":
            style_counter[block["style"] or "<空样式>"] += 1

    print(f"总块数: {len(blocks)}\n")

    print("类型分布:")
    for t, c in type_counter.most_common():
        pct = c / len(blocks) * 100
        print(f"  {t:12s} {c:4d}  ({pct:.1f}%)")

    print(f"\n段落样式分布({len(style_counter)} 种):")
    for style, count in style_counter.most_common():
        pct = count / type_counter.get("paragraph", 1) * 100
        print(f"  {style:30s} {count:4d}  ({pct:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python inspect_styles.py 某标准.docx")
        sys.exit(1)
    main(sys.argv[1])
