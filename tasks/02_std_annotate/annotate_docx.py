"""
标注脚本:批量处理 word 文档,在识别的节标题段落前插入分块标识符

流程:
1. 扫 INPUT_DIR 下所有 .docx
2. 每份文档:
   a. word_parser 提取块列表
   b. format_for_annotation 格式化
   c. 超长则分块调用模型,带重叠
   d. 合并结果、按段落编号去重
   e. 用 python-docx 在对应段落前插入 <<<SECTION>>>
   f. 保存到 OUTPUT_DIR
3. 每份处理完写一份 JSON 结果到 items/,带疑似边界标记
4. 失败也写 JSON,带 _status: failed 标记,断点续跑

依赖:
    openai
    python-docx
    word_parser.py (同目录)
    annotation_prompt.py (同目录)
"""
import os
import sys
import json
import time
from datetime import datetime
from openai import OpenAI
from docx import Document

from word_parser import parse_docx, format_for_annotation
from annotation_prompt import PROMPT_TEMPLATE, JSON_SCHEMA

sys.stdout.reconfigure(line_buffering=True)

# ============= 配置区 =============
BASE_URL   = "http://a.b.c.d:e/v1"
MODEL_NAME = "Qwen3.5-35B-A3B"
API_KEY    = ""

INPUT_DIR       = r"C:\std_gov\input_docx"
OUTPUT_DIR      = r"C:\std_gov\output_docx"
ITEMS_DIR       = r"C:\std_gov\annotation_items"   # 模型结果 JSON 存这里

SECTION_MARKER  = "<<<SECTION>>>"

# 分块参数
MAX_CHARS_PER_CALL = 80000    # 单次调用最大字符数(约 80K token,留 20K buffer)
OVERLAP_BLOCKS     = 20       # 分块重叠的块数

REQUEST_TIMEOUT = 600
MAX_TOKENS      = 8192
# ==================================

client = OpenAI(
    api_key=API_KEY or "not-needed",
    base_url=BASE_URL,
    timeout=REQUEST_TIMEOUT,
)


def extract_first_json(raw: str) -> str:
    """从模型输出里提取第一个完整 JSON 对象(兜底用)"""
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


def call_model(formatted_text: str) -> dict:
    """单次调用模型,返回解析后的 JSON"""
    prompt = PROMPT_TEMPLATE.replace("__DOCUMENT_TEXT__", formatted_text)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=MAX_TOKENS,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "annotation_schema",
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
    return json.loads(cleaned)


def split_blocks_for_chunks(blocks: list[dict], max_chars: int, overlap: int) -> list[tuple[int, int]]:
    """把块列表切成多段调用范围,返回 [(start_idx, end_idx), ...] 的列表(end 不包含)

    每段格式化后的字符数不超过 max_chars,相邻段有 overlap 个块的重叠。
    如果整篇能塞下就返回单段 [(0, len(blocks))]。
    """
    formatted_full = format_for_annotation(blocks)
    if len(formatted_full) <= max_chars:
        return [(0, len(blocks))]

    # 简单策略:按段落数对半切,必要时继续拆
    # 先估算平均每段字符数
    n = len(blocks)
    ranges = []
    start = 0
    while start < n:
        # 二分找最大 end 使格式化字符数 <= max_chars
        low, high = start + 1, n
        best_end = start + 1
        while low <= high:
            mid = (low + high) // 2
            chunk_text = format_for_annotation(blocks[start:mid])
            if len(chunk_text) <= max_chars:
                best_end = mid
                low = mid + 1
            else:
                high = mid - 1
        ranges.append((start, best_end))
        if best_end >= n:
            break
        # 下一段的 start 向前回退 overlap
        start = max(best_end - overlap, start + 1)
    return ranges


def annotate_document(blocks: list[dict]) -> dict:
    """对一份文档做识别,返回合并后的结果

    返回字段:
    - 标准名称
    - 节标记列表:合并去重后的所有标记
    - 统计:从合并结果算出
    - 疑似边界:落在分块重叠区的标记列表(供人工复核)
    - 分块信息:分了几段,每段的范围
    """
    ranges = split_blocks_for_chunks(blocks, MAX_CHARS_PER_CALL, OVERLAP_BLOCKS)

    all_markers = []          # 合并所有段的标记
    seen_ids = set()          # 去重用
    ambiguous = []            # 落在重叠区的疑似标记
    standard_name = ""
    chunk_infos = []

    # 先算出所有重叠区的段落编号集合
    overlap_ids = set()
    for i in range(len(ranges) - 1):
        cur_end = ranges[i][1]
        next_start = ranges[i + 1][0]
        # 重叠区是 [next_start, cur_end)
        for idx in range(next_start, cur_end):
            overlap_ids.add(blocks[idx]["id"])

    for seg_idx, (start, end) in enumerate(ranges):
        sub_blocks = blocks[start:end]
        sub_text = format_for_annotation(sub_blocks)
        print(f"    调用模型 段{seg_idx + 1}/{len(ranges)} "
              f"(块 {start}-{end}, 字符数 {len(sub_text)})")
        result = call_model(sub_text)

        # 第一段的标准名称作为全文的标准名称
        if seg_idx == 0 and result.get("标准名称"):
            standard_name = result["标准名称"]

        chunk_infos.append({
            "段号": seg_idx + 1,
            "块范围": f"{blocks[start]['id']}-{blocks[end - 1]['id']}",
            "识别出的标记数": len(result.get("节标记列表", [])),
        })

        for marker in result.get("节标记列表", []):
            pid = marker.get("段落编号", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_markers.append(marker)
            if pid in overlap_ids:
                ambiguous.append({**marker, "所在段号": seg_idx + 1})

    # 按段落编号排序(P0001 < P0002)
    all_markers.sort(key=lambda m: m.get("段落编号", ""))

    # 重算统计
    low_count = sum(1 for m in all_markers if m.get("置信度") == "低")
    stats = {
        "总段落数": len(blocks),
        "标记段落数": len(all_markers),
        "低置信度数": low_count,
    }

    return {
        "标准名称": standard_name,
        "节标记列表": all_markers,
        "统计": stats,
        "疑似边界": ambiguous,
        "分块信息": chunk_infos,
    }


def insert_markers_into_docx(
    input_path: str,
    output_path: str,
    blocks: list[dict],
    markers: list[dict],
) -> int:
    """在 word 文档的对应段落前插入 <<<SECTION>>>

    做法:新增一个段落(含 SECTION_MARKER 文本)插在目标段落前。
    方案 C("同段前加标识")改为"新增一段"是因为 python-docx 修改同段较复杂,
    且 HiAgent 按 XML 切时独立段更稳。

    返回实际插入的标记数。
    """
    marker_ids = set(m.get("段落编号", "") for m in markers)
    if not marker_ids:
        # 没有要插的,直接复制文件
        import shutil
        shutil.copy(input_path, output_path)
        return 0

    doc = Document(input_path)

    # 重新遍历 body,按与 word_parser 相同的顺序找到对应 paragraph 对象
    # 这里必须用同样的遍历逻辑,保证编号一致
    from docx.oxml.ns import qn
    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    TAG_P = f"{{{W_NS}}}p"
    TAG_TBL = f"{{{W_NS}}}tbl"

    body = doc.element.body
    paragraph_map = {p._element: p for p in doc.paragraphs}

    # 先收集所有要插标记的目标段落
    targets = []
    index = 0
    for child in body.iterchildren():
        if child.tag == TAG_P:
            paragraph = paragraph_map.get(child)
            if paragraph is None:
                continue
            index += 1
            pid = f"P{index:04d}"
            if pid in marker_ids:
                targets.append(paragraph)
        elif child.tag == TAG_TBL:
            index += 1
            # 表格不会被标记为节边界,略过

    # 对每个目标段落,在其前面插入一个新段落,内容为 marker
    inserted = 0
    for target in targets:
        new_para = target.insert_paragraph_before(SECTION_MARKER)
        # 新段落用默认样式,不继承 target 的样式(避免 marker 也变成 Heading)
        try:
            new_para.style = doc.styles["Normal"]
        except KeyError:
            pass
        inserted += 1

    doc.save(output_path)
    return inserted


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


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


def rel_path_to_item_name(rel_path: str) -> str:
    name = rel_path
    if name.lower().endswith(".docx"):
        name = name[:-5]
    name = name.replace("/", "_").replace("\\", "_")
    return name + ".json"


def rel_path_to_output_path(rel_path: str, output_dir: str) -> str:
    """输出目录结构保持和输入一致"""
    return os.path.join(output_dir, rel_path)


def batch_annotate():
    os.makedirs(ITEMS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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
            output_path = rel_path_to_output_path(rel_path, OUTPUT_DIR)
            pending.append((path, rel_path, item_path, output_path))

    total = len(docx_files)
    print(f"共 {total} 个 .docx,已完成 {skipped} 个,待处理 {len(pending)} 个\n")
    if not pending:
        print("所有文件已处理完成")
        return

    batch_start = time.time()
    success_cnt = 0
    fail_cnt = 0

    for idx, (src_path, rel_path, item_path, output_path) in enumerate(pending, 1):
        size_kb = os.path.getsize(src_path) / 1024
        print(f"[{idx}/{len(pending)}] {rel_path} ({size_kb:.1f} KB)")

        t0 = time.time()
        try:
            # 1. 解析
            blocks = parse_docx(src_path)
            print(f"    解析完成: {len(blocks)} 个块")

            # 2. 调模型识别
            result = annotate_document(blocks)
            markers = result["节标记列表"]
            print(f"    识别完成: {len(markers)} 个节边界 "
                  f"(低置信度 {result['统计']['低置信度数']},"
                  f" 疑似边界 {len(result['疑似边界'])})")

            # 3. 插标识
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            inserted = insert_markers_into_docx(src_path, output_path, blocks, markers)
            print(f"    已写入 {output_path} (插入 {inserted} 个标识)")

            # 4. 落盘结果 JSON
            result["source_file"] = rel_path
            result["output_file"] = os.path.relpath(output_path, OUTPUT_DIR)
            write_success(item_path, result)
            success_cnt += 1
            print(f"    ✓ 完成 (耗时 {fmt_duration(time.time() - t0)})")

        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            write_failure(item_path, rel_path, err)
            fail_cnt += 1
            print(f"    ✗ 失败 (耗时 {fmt_duration(time.time() - t0)}): {err}")

    print(f"\n本轮完成,总耗时 {fmt_duration(time.time() - batch_start)}")
    print(f"成功 {success_cnt} 份,失败 {fail_cnt} 份")
    print(f"标注后的 word 存于: {OUTPUT_DIR}")
    print(f"识别结果 JSON 存于: {ITEMS_DIR}")


if __name__ == "__main__":
    batch_annotate()
