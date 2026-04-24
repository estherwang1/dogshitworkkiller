"""
摘要生成脚本(word 版)

批量读 word 文档,生成"一句话概括 + 文档摘要",每份落一份 JSON 到 ITEMS_DIR,
支持断点续跑。

依赖:
    openai
    python-docx
    word_parser.py (同目录)
    summary_prompt.py (同目录)

PROMPT 和 JSON_SCHEMA 不在本文件,见 summary_prompt.py。
"""
import os
import sys
import json
import time
from datetime import datetime
from openai import OpenAI

from word_parser import parse_docx, join_for_evaluation
from summary_prompt import PROMPT_TEMPLATE, JSON_SCHEMA

sys.stdout.reconfigure(line_buffering=True)

# ============= 配置区 =============
BASE_URL   = "http://a.b.c.d:e/v1"
MODEL_NAME = "Qwen3.5-35B-A3B"
API_KEY    = ""

INPUT_DIR  = r"C:\std_gov\input_docx"
ITEMS_DIR  = r"C:\std_gov\summary_items"

LONG_DOC_THRESHOLD_CHARS = 180000
REQUEST_TIMEOUT = 600
MAX_TOKENS      = 1024   # 摘要输出很短,1K token 够用
# ==================================

client = OpenAI(
    api_key=API_KEY or "not-needed",
    base_url=BASE_URL,
    timeout=REQUEST_TIMEOUT,
)


def extract_first_json(raw: str) -> str:
    """兜底:从模型输出里提取第一个完整 JSON 对象"""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    start = s.find("{")
    if start == -1:
        raise ValueError("未找到 JSON 起始标记")
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(s)):
        c = s[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    raise ValueError("JSON 括号不匹配")


def summarize_document(text: str, fallback_name: str) -> dict:
    prompt = PROMPT_TEMPLATE.replace("__DOCUMENT_TEXT__", text)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,      # 摘要允许稍微有点变化,0.3 比评估的 0.1 松
        max_tokens=MAX_TOKENS,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "summary_schema",
                "schema": JSON_SCHEMA,
                "strict": True,
            },
        },
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    if response.choices[0].finish_reason == "length":
        raise ValueError("输出被截断,max_tokens 不够")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("模型返回为空")
    cleaned = extract_first_json(content)
    result = json.loads(cleaned)
    if not result.get("标准名称"):
        result["标准名称"] = fallback_name
    return result


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def rel_path_to_item_name(rel_path: str) -> str:
    name = rel_path
    if name.lower().endswith(".docx"):
        name = name[:-5]
    name = name.replace("/", "_").replace("\\", "_")
    return name + ".json"


def is_item_complete(item_path: str) -> bool:
    if not os.path.isfile(item_path):
        return False
    try:
        with open(item_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    if isinstance(data, dict) and data.get("_status") == "failed":
        return False
    return True


def write_success(item_path: str, result: dict):
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def write_failure(item_path: str, rel_path: str, error_msg: str):
    payload = {
        "source_file": rel_path,
        "_status": "failed",
        "_error": error_msg,
        "_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def batch_summarize():
    os.makedirs(ITEMS_DIR, exist_ok=True)

    docx_files = []
    for root, _dirs, filenames in os.walk(INPUT_DIR):
        for fname in filenames:
            if fname.lower().endswith(".docx") and not fname.startswith("~$"):
                docx_files.append(os.path.join(root, fname))
    docx_files.sort()
    if not docx_files:
        print(f"在 {INPUT_DIR} 下未找到 .docx 文件")
        return

    pending = []
    skipped = 0
    for path in docx_files:
        rel_path = os.path.relpath(path, INPUT_DIR)
        item_path = os.path.join(ITEMS_DIR, rel_path_to_item_name(rel_path))
        if is_item_complete(item_path):
            skipped += 1
        else:
            pending.append((path, rel_path, item_path))

    total = len(docx_files)
    print(f"共 {total} 个 .docx,已完成 {skipped} 个,待处理 {len(pending)} 个\n")
    if not pending:
        print("所有文件已处理完成")
        return

    batch_start = time.time()
    success_cnt = 0
    fail_cnt = 0

    for idx, (src_path, rel_path, item_path) in enumerate(pending, 1):
        size_kb = os.path.getsize(src_path) / 1024
        print(f"[{idx}/{len(pending)}] 摘要: {rel_path} ({size_kb:.1f} KB)")

        t0 = time.time()
        try:
            blocks = parse_docx(src_path)
            text = join_for_evaluation(blocks)

            if not text.strip():
                write_failure(item_path, rel_path, "提取后文本为空")
                fail_cnt += 1
                print(f"  跳过空文本")
                continue

            if len(text) > LONG_DOC_THRESHOLD_CHARS:
                print(f"  ⚠ 文档较长({len(text)} 字符),摘要可能偏颇,建议人工核查")

            fallback_name = os.path.splitext(os.path.basename(src_path))[0]
            result = summarize_document(text, fallback_name)
            result["source_file"] = rel_path
            write_success(item_path, result)
            success_cnt += 1
            print(f"  ✓ 摘要完成 (耗时 {fmt_duration(time.time() - t0)})")

        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            write_failure(item_path, rel_path, err)
            fail_cnt += 1
            print(f"  ✗ 摘要失败 (耗时 {fmt_duration(time.time() - t0)}): {err}")

    print(f"\n本轮完成,总耗时 {fmt_duration(time.time() - batch_start)}")
    print(f"成功 {success_cnt} 份,失败 {fail_cnt} 份")
    print(f"结果存于: {ITEMS_DIR}")


if __name__ == "__main__":
    batch_summarize()
