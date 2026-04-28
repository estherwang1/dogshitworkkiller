"""任务 02:标准规范分块标注

读 docx 文档,识别节边界,在 docx 对应位置插入分块标识符,产出供
HiAgent 知识库分块用的新 docx。

特殊性:
- 长文档需要分块调用 LLM(单次调用 token 不够),含重叠区
- 输出有两份:JSON(识别结果)+ 修改后的 docx(主交付物)

支持两种启动方式(见编码规范 3.4 节):

    # 启动器调用,传任务目录:
    python tasks/02_std_annotate/runner.py tasks/02_std_annotate

    # 独立运行,从脚本所在目录读 config:
    cd tasks/02_std_annotate && python runner.py
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 任务专属模块的目录也加到 sys.path,方便 import chunker/docx_writer
TASK_DIR = Path(__file__).resolve().parent
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from shared.batch_runner import run_batch
from shared.config_loader import load_config
from shared.llm_client import LLMClient
from shared.word_parser import format_for_annotation, parse_docx

from chunker import merge_chunk_results, split_into_chunks
from docx_writer import insert_section_markers


sys.stdout.reconfigure(line_buffering=True)


def _load_prompt_template(task_dir: Path) -> str:
    return (task_dir / "prompt.md").read_text(encoding="utf-8")


def _load_schema(task_dir: Path) -> dict:
    with (task_dir / "schema.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_task_dir() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    return Path(__file__).resolve().parent


def main():
    task_dir = _resolve_task_dir()
    config = load_config(task_dir / "config.yaml")

    prompt_template = _load_prompt_template(task_dir)
    schema = _load_schema(task_dir)

    llm = LLMClient(
        base_url=config["llm_base_url"],
        api_key=config.get("llm_api_key", ""),
        model=config["llm_model_name"],
        timeout=config.get("llm_timeout", 600),
    )

    max_tokens = config.get("llm_max_tokens", 8192)
    temperature = config.get("llm_temperature", 0.1)
    extra_body = config.get("llm_extra_body")
    max_chars_per_call = config.get("max_chars_per_call", 80000)
    overlap_blocks = config.get("overlap_blocks", 20)

    input_dir = Path(config["input_dir"])
    output_items_dir = Path(config["output_items_dir"])
    output_docx_dir = Path(config["output_docx_dir"])

    def call_llm(formatted_text: str) -> dict:
        prompt = prompt_template.replace("__DOCUMENT_TEXT__", formatted_text)
        return llm.call_json(
            prompt,
            schema,
            schema_name="annotation_schema",
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )

    def handler(input_path: Path) -> dict:
        # 1. 解析 docx
        blocks = parse_docx(str(input_path))
        if not blocks:
            raise ValueError("解析后无任何块")
        print(f"  解析完成: {len(blocks)} 个块")

        # 2. 切分调用范围
        ranges = split_into_chunks(blocks, max_chars=max_chars_per_call, overlap=overlap_blocks)

        # 3. 多次调用模型
        chunk_results = []
        for seg_idx, (start, end) in enumerate(ranges):
            sub_blocks = blocks[start:end]
            sub_text = format_for_annotation(sub_blocks)
            print(
                f"  调用模型 段{seg_idx + 1}/{len(ranges)} "
                f"(块 {start}-{end}, 字符数 {len(sub_text)})"
            )
            chunk_results.append(call_llm(sub_text))

        # 4. 合并结果
        merged = merge_chunk_results(blocks, ranges, chunk_results)
        markers = merged["节标记列表"]
        print(
            f"  识别完成: {len(markers)} 个节边界 "
            f"(低置信度 {merged['统计']['低置信度数']},"
            f" 疑似边界 {len(merged['疑似边界'])})"
        )

        # 5. 把标记插回 docx,落到 output_docx_dir 保留相对路径
        rel_path = input_path.relative_to(input_dir)
        output_docx_path = output_docx_dir / rel_path
        inserted = insert_section_markers(input_path, output_docx_path, blocks, markers)
        print(f"  已写入 {output_docx_path} (插入 {inserted} 个标识)")

        # 6. 标准名称兜底
        if not merged.get("标准名称"):
            merged["标准名称"] = input_path.stem

        # 把输出 docx 路径记到结果里,方便人工核对
        merged["output_docx"] = str(rel_path)
        return merged

    run_batch(
        input_dir=input_dir,
        output_items_dir=output_items_dir,
        handler=handler,
        file_pattern="*.docx",
        exclude_prefixes=("~$",),
    )


if __name__ == "__main__":
    main()
