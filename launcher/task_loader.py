"""任务发现
扫 tasks/ 目录,读各任务的 task.yaml,返回任务元信息列表。

每个任务的元信息包含:
- name: 显示名
- description: 一句话说明
- entry: 主入口脚本(相对任务目录)
- actions: 附加操作列表(可选)
- version: 版本号
- task_dir: 任务目录的绝对路径(由本模块补充,不来自 task.yaml)
"""

from pathlib import Path
import yaml
from encoding_utils import safe_open


def discover_tasks(project_root: Path) -> list[dict]:
    """扫描 project_root/tasks/ 下的子目录,返回任务元信息列表。

    只收集含 task.yaml 的直接子目录,按目录名排序。
    task.yaml 读取失败的目录会被跳过并打印警告。

    Args:
        project_root: 项目根目录。

    Returns:
        任务元信息列表,每项是 task.yaml 的内容加上 task_dir 字段。
        tasks/ 不存在或无有效任务时返回空列表。
    """
    tasks_dir = project_root / "tasks"
    if not tasks_dir.is_dir():
        return []

    tasks = []
    for child in sorted(tasks_dir.iterdir()):
        if not child.is_dir():
            continue
        task_yaml = child / "task.yaml"
        if not task_yaml.is_file():
            continue
        try:
            with safe_open(task_yaml, "r") as f:
                meta = yaml.safe_load(f)
            if not isinstance(meta, dict):
                print(f" ⚠ {task_yaml}: 顶层不是 dict,跳过")
                continue
        except Exception as e:
            print(f" ⚠ {task_yaml}: 读取失败 ({e}),跳过")
            continue

        meta["task_dir"] = child.resolve()

        # 确保基本字段存在
        meta.setdefault("name", child.name)
        meta.setdefault("description", "")
        meta.setdefault("entry", "runner.py")
        meta.setdefault("actions", [])
        meta.setdefault("version", "")

        tasks.append(meta)

    return tasks
