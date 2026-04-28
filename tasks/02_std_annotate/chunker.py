"""分块调用切分与结果合并

标注任务的特殊需求:文档可能很长,模型一次输出 token 撑不下,需要把文档
按段落切成多次调用,相邻调用之间留重叠区,最后合并去重。

三个对外函数:
- split_into_chunks: 切分调用范围
- find_overlap_block_ids: 算重叠区段落 id 集合
- merge_chunk_results: 合并多次调用结果,标记疑似边界

任务 02 专属模块,不进 shared(其他任务无此需求)。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.word_parser import format_for_annotation


def split_into_chunks(
    blocks: list[dict],
    max_chars: int,
    overlap: int,
) -> list[tuple[int, int]]:
    """把段落列表切成多段调用范围,每段格式化后不超过 max_chars。

    Args:
        blocks: word_parser.parse_docx() 的输出。
        max_chars: 单段格式化文本最大字符数。
        overlap: 相邻段重叠的段落数(用于让模型能看到边界附近的上下文)。

    Returns:
        [(start, end), ...] 列表,end 不含。整篇能塞下时返回单段
        [(0, len(blocks))]。

    Raises:
        ValueError: blocks 为空 / max_chars / overlap 不合理。
    """
    if not blocks:
        raise ValueError("blocks 为空")
    if max_chars <= 0:
        raise ValueError(f"max_chars 必须为正:{max_chars}")
    if overlap < 0:
        raise ValueError(f"overlap 不能为负:{overlap}")

    n = len(blocks)
    full_text = format_for_annotation(blocks)
    if len(full_text) <= max_chars:
        return [(0, n)]

    ranges: list[tuple[int, int]] = []
    start = 0
    while start < n:
        # 二分找最大 end 使 blocks[start:end] 的格式化字符数 <= max_chars
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
        # 下一段往前回退 overlap 个段落,但保证起码前进一步避免死循环
        start = max(best_end - overlap, start + 1)
    return ranges


def find_overlap_block_ids(
    blocks: list[dict],
    ranges: list[tuple[int, int]],
) -> set[str]:
    """从调用范围列表算出所有重叠区段落 id 集合。

    重叠区指:第 i 段的尾部和第 i+1 段的头部覆盖的相同段落。
    具体计算为 [next_start, cur_end) 范围内的段落 id。

    Args:
        blocks: 段落块列表。
        ranges: split_into_chunks 返回的范围列表。

    Returns:
        重叠区段落 id 的集合(可能为空,表示没有重叠或只有一段)。
    """
    overlap_ids: set[str] = set()
    for i in range(len(ranges) - 1):
        cur_end = ranges[i][1]
        next_start = ranges[i + 1][0]
        # 重叠区 = [next_start, cur_end),正常情况 next_start < cur_end
        for idx in range(next_start, cur_end):
            if 0 <= idx < len(blocks):
                overlap_ids.add(blocks[idx]["id"])
    return overlap_ids


def merge_chunk_results(
    blocks: list[dict],
    ranges: list[tuple[int, int]],
    chunk_results: list[dict],
) -> dict:
    """合并多次模型调用的结果。

    合并规则:
    - 标准名称:取第一段返回的(空也无所谓,后处理用文件名兜底)
    - 节标记列表:合并去重(按段落编号),按编号排序
    - 疑似边界:落在重叠区内的标记,带"所在段号"字段供人工核查
    - 统计:按合并后实际数据重算
    - 分块信息:每段的范围 + 该段识别出的标记数,供调试

    Args:
        blocks: 完整段落列表。
        ranges: 调用范围列表(必须和 chunk_results 一一对应)。
        chunk_results: 每段一次调用的返回 dict 列表。

    Returns:
        合并后的最终结果 dict。
    """
    if len(ranges) != len(chunk_results):
        raise ValueError(
            f"ranges 和 chunk_results 长度不一致:{len(ranges)} vs {len(chunk_results)}"
        )

    overlap_ids = find_overlap_block_ids(blocks, ranges)
    standard_name = ""
    seen_ids: set[str] = set()
    all_markers: list[dict] = []
    ambiguous: list[dict] = []
    chunk_infos: list[dict] = []

    for seg_idx, ((start, end), result) in enumerate(zip(ranges, chunk_results)):
        # 标准名称取第一段
        if seg_idx == 0:
            standard_name = result.get("标准名称", "") or ""

        markers = result.get("节标记列表", [])
        if not isinstance(markers, list):
            markers = []

        # 段范围信息
        if start < len(blocks) and end - 1 < len(blocks) and end > start:
            range_str = f"{blocks[start]['id']}-{blocks[end - 1]['id']}"
        else:
            range_str = f"{start}-{end}"
        chunk_infos.append({
            "段号": seg_idx + 1,
            "块范围": range_str,
            "识别出的标记数": len(markers),
        })

        # 去重合并
        for marker in markers:
            if not isinstance(marker, dict):
                continue
            pid = marker.get("段落编号", "")
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_markers.append(marker)
            if pid in overlap_ids:
                ambiguous.append({**marker, "所在段号": seg_idx + 1})

    all_markers.sort(key=lambda m: m.get("段落编号", ""))

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
