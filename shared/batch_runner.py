"""批量处理框架

承担三件事,把任务侧从样板代码里解放出来:

1. 扫输入目录,得到待处理文件列表
2. 断点续跑:已完成的输出 JSON 自动跳过
3. 单份失败不影响整体,失败信息独立落 JSON

任务侧只需提供一个回调函数:接收输入文件路径,返回要落盘的结果 dict。

典型用法:
    from pathlib import Path
    from shared.batch_runner import run_batch

    def handler(input_path: Path) -> dict:
        # 解析、调 LLM、返回结果
        ...
        return {"标准名称": ..., "硬约束": ..., ...}

    run_batch(
        input_dir=Path("..."),
        output_items_dir=Path("..."),
        handler=handler,
        file_pattern="*.docx",
        exclude_prefixes=("~$",),
    )
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# -------- 私有工具函数 --------

def _list_input_files(
    input_dir: Path,
    pattern: str,
    exclude_prefixes: tuple,
) -> list[Path]:
    """递归扫描输入目录,按文件名排序。"""
    files = []
    for path in input_dir.rglob(pattern):
        if not path.is_file():
            continue
        if any(path.name.startswith(p) for p in exclude_prefixes):
            continue
        files.append(path)
    files.sort()
    return files


def _input_to_item_name(input_path: Path, relative_root: Path) -> str:
    """根据输入文件相对路径,算出对应的输出 JSON 文件名。

    路径分隔符替换为下划线,扁平化到单一目录。
    例如 "subdir/foo.docx" -> "subdir_foo.json"。
    """
    rel = input_path.relative_to(relative_root)
    parts = list(rel.parts)
    parts[-1] = rel.stem  # 去掉扩展名
    return "_".join(parts) + ".json"


def _is_complete(item_path: Path) -> bool:
    """已存在且非 failed 状态视为已完成。"""
    if not item_path.is_file():
        return False
    try:
        with item_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    if isinstance(data, dict) and data.get("_status") == "failed":
        return False
    return True


def _write_success(item_path: Path, source_file: str, result: dict):
    """写成功结果。如果 result 没有 source_file 字段,自动补上。"""
    payload = dict(result)
    payload.setdefault("source_file", source_file)
    item_path.parent.mkdir(parents=True, exist_ok=True)
    with item_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _write_failure(item_path: Path, source_file: str, error_msg: str):
    """写失败结果。"""
    payload = {
        "source_file": source_file,
        "_status": "failed",
        "_error": error_msg,
        "_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    item_path.parent.mkdir(parents=True, exist_ok=True)
    with item_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def _fmt_size(bytes_count: int) -> str:
    if bytes_count < 1024:
        return f"{bytes_count} B"
    if bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    if bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / 1024 / 1024:.1f} MB"
    return f"{bytes_count / 1024 / 1024 / 1024:.1f} GB"


# -------- 公共入口 --------

def run_batch(
    *,
    input_dir: Path,
    output_items_dir: Path,
    handler: Callable[[Path], dict],
    file_pattern: str = "*",
    exclude_prefixes: tuple = (),
) -> dict:
    """批量处理入口。

    Args:
        input_dir: 输入文件根目录(递归扫描)。
        output_items_dir: 输出 JSON 目录,每份输入对应一份 JSON。
        handler: 业务回调函数,签名为 (Path) -> dict。
            handler 抛任何异常都会被捕获,转为 failed JSON,不影响其他文件。
            handler 返回的 dict 会被原样写入 JSON,如果不含 source_file 字段
            会自动补上。
        file_pattern: glob 模式,如 "*.docx" / "*.pdf"。
        exclude_prefixes: 排除以这些前缀开头的文件名,如 ("~$",) 排除 word
            临时文件。

    Returns:
        统计字典:{"total", "skipped", "succeeded", "failed"}。
    """
    input_dir = Path(input_dir)
    output_items_dir = Path(output_items_dir)
    output_items_dir.mkdir(parents=True, exist_ok=True)

    all_files = _list_input_files(input_dir, file_pattern, exclude_prefixes)

    if not all_files:
        print(f"在 {input_dir} 下未找到匹配 {file_pattern} 的文件")
        return {"total": 0, "skipped": 0, "succeeded": 0, "failed": 0}

    pending = []
    skipped = 0
    for src_path in all_files:
        item_name = _input_to_item_name(src_path, input_dir)
        item_path = output_items_dir / item_name
        if _is_complete(item_path):
            skipped += 1
        else:
            pending.append((src_path, item_path))

    total = len(all_files)
    print(f"共 {total} 个文件,已完成 {skipped} 个,待处理 {len(pending)} 个\n")

    if not pending:
        print("所有文件已处理完成")
        return {"total": total, "skipped": skipped, "succeeded": 0, "failed": 0}

    batch_start = time.time()
    succeeded = 0
    failed = 0

    for idx, (src_path, item_path) in enumerate(pending, 1):
        rel = src_path.relative_to(input_dir)
        size_str = _fmt_size(src_path.stat().st_size)
        print(f"[{idx}/{len(pending)}] {rel} ({size_str})")

        t0 = time.time()
        try:
            result = handler(src_path)
            _write_success(item_path, str(rel), result)
            succeeded += 1
            print(f"  ✓ 完成 (耗时 {_fmt_duration(time.time() - t0)})")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            _write_failure(item_path, str(rel), err)
            failed += 1
            print(f"  ✗ 失败 (耗时 {_fmt_duration(time.time() - t0)}): {err}")

    print(f"\n本轮完成,总耗时 {_fmt_duration(time.time() - batch_start)}")
    print(f"成功 {succeeded} 份,失败 {failed} 份")
    print(f"结果存于: {output_items_dir}")

    return {
        "total": total,
        "skipped": skipped,
        "succeeded": succeeded,
        "failed": failed,
    }
