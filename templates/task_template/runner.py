"""任务 NN:任务名称

[一两句话说明这个任务做什么]

支持两种启动方式(见编码规范 3.4 节):

    # 启动器调用,传任务目录:
    python tasks/NN_task_name/runner.py tasks/NN_task_name

    # 独立运行,从脚本所在目录读 config:
    cd tasks/NN_task_name && python runner.py
"""
import json
import sys
from pathlib import Path

# 把项目根目录加入 sys.path,让 shared 可被 import
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.config_loader import load_config
from shared.llm_client import LLMClient
from shared.batch_runner import run_batch
from shared.word_parser import parse_docx, join_for_evaluation


# 让启动器能实时捕获日志(见编码规范 3.5 节)
sys.stdout.reconfigure(line_buffering=True)


def _load_prompt_template(task_dir: Path) -> str:
    """读 prompt.md 全文作为模板,文本内含 __DOCUMENT_TEXT__ 占位符"""
    return (task_dir / "prompt.md").read_text(encoding="utf-8")


def _load_schema(task_dir: Path) -> dict:
    """读 schema.json"""
    with (task_dir / "schema.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_task_dir() -> Path:
    """启动器传入参数则用之,否则用脚本所在目录"""
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

    threshold_long = config.get("threshold_long_doc_chars", 180000)
    max_tokens = config.get("llm_max_tokens", 4096)
    temperature = config.get("llm_temperature", 0.1)
    extra_body = config.get("llm_extra_body")

    def handler(input_path: Path) -> dict:
        # --- 在这里写你的业务逻辑 ---

        # 1. 解析输入(按需修改,不一定是 docx)
        blocks = parse_docx(str(input_path))
        text = join_for_evaluation(blocks)
        if not text.strip():
            raise ValueError("提取后文本为空")
        if len(text) > threshold_long:
            print(f"  ⚠ 文档较长({len(text)} 字符),建议人工核查")

        # 2. 调用 LLM
        prompt = prompt_template.replace("__DOCUMENT_TEXT__", text)
        result = llm.call_json(
            prompt,
            schema,
            schema_name="response",
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )

        # 3. 后处理(按需修改)
        if not result.get("示例字段"):
            result["示例字段"] = input_path.stem

        return result

    run_batch(
        input_dir=Path(config["input_dir"]),
        output_items_dir=Path(config["output_items_dir"]),
        handler=handler,
        file_pattern="*.docx",
        exclude_prefixes=("~$",),
    )


if __name__ == "__main__":
    main()
