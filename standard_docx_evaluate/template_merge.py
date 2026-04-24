"""
合并脚本模板:扫描 items/ 目录下所有单份 JSON,合并成一份 merged.json

配套批量调用模板使用。批量模板每跑完一份就写一个单独的 JSON 文件,
本脚本把它们汇总成一个数组,便于后续统一处理(转 Excel、人工查看等)。

使用方法:
1. 改下方【配置区】的两个路径
2. 运行: python.exe 本文件名.py

输出:
- OUTPUT_DIR 下生成 merged.json,包含所有单份结果
- 失败的条目(_status: failed)也保留,方便人工识别哪些需要重跑
"""
import os
import sys
import json
import glob

sys.stdout.reconfigure(line_buffering=True)

# ============= 配置区:改这里 =============
ITEMS_DIR   = r"C:\你的输出文件夹\items"    # ← 单份 JSON 所在目录(批量脚本的 OUTPUT_DIR/items)
MERGED_FILE = r"C:\你的输出文件夹\merged.json"  # ← 合并结果保存位置
# =========================================


def merge():
    if not os.path.isdir(ITEMS_DIR):
        print(f"未找到目录: {ITEMS_DIR}")
        print("请先运行批量调用脚本生成 items/ 目录")
        return

    pattern = os.path.join(ITEMS_DIR, "*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"{ITEMS_DIR} 下没有 JSON 文件")
        return

    merged = []
    bad_files = []   # 文件本身损坏(读不出来)的
    success_cnt = 0
    fail_cnt = 0

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            bad_files.append((os.path.basename(path), str(e)))
            continue

        merged.append(data)
        if isinstance(data, dict) and data.get("_status") == "failed":
            fail_cnt += 1
        else:
            success_cnt += 1

    os.makedirs(os.path.dirname(MERGED_FILE) or ".", exist_ok=True)
    with open(MERGED_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"合并完成: {MERGED_FILE}")
    print(f"  条目总数: {len(merged)}")
    print(f"  成功: {success_cnt}")
    print(f"  失败(已标记): {fail_cnt}")
    if bad_files:
        print(f"  文件损坏(无法读取,未纳入): {len(bad_files)}")
        for name, err in bad_files:
            print(f"    - {name}: {err}")


if __name__ == "__main__":
    merge()
