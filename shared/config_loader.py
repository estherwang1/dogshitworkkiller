"""配置文件加载

读 YAML 配置文件返回 dict。

设计上保持极薄:只做"读文件 + 顶层结构校验",不做字段类型校验。
字段类型校验需要 schema(config.schema.yaml),后续启动器或任务侧
按需取用,本模块不掺合。

任务侧用法:
    from shared.config_loader import load_config

    config = load_config(task_dir / "config.yaml")
    input_dir = Path(config["input_dir"])
"""
from pathlib import Path

import yaml


def load_config(config_path) -> dict:
    """读 YAML 配置文件,返回顶层 dict。

    Args:
        config_path: 配置文件路径(str 或 Path)。

    Returns:
        解析后的字典。空文件返回空 dict。

    Raises:
        FileNotFoundError: 文件不存在。
        yaml.YAMLError: YAML 解析失败。
        ValueError: 顶层结构不是 dict(例如顶层是数组或标量)。
    """
    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"配置文件顶层应为映射(dict),实际为 {type(data).__name__}: {config_path}"
        )
    return data
