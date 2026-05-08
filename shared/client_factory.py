"""LLM 客户端工厂

根据配置字典里的 llm_backend 字段,创建对应的客户端实例。
调用方拿到的对象都有 call_json 方法,不需要关心底层是哪个实现。

典型用法:
    from shared.client_factory import create_llm_client

    client = create_llm_client(config)
    result = client.call_json(prompt, schema)
"""
from .llm_client import LLMClient
from .hiagent_client import HiAgentClient


def create_llm_client(config: dict):
    """根据配置创建 LLM 客户端实例。

    Args:
        config: 任务的 config.yaml 解析后的字典。

    根据 config["llm_backend"] 的值:
    - "openai"(默认): 创建 LLMClient,读 llm_base_url / llm_api_key /
      llm_model_name / llm_timeout
    - "hiagent": 创建 HiAgentClient,读 hiagent_base_url / hiagent_api_key /
      hiagent_user_id / llm_timeout

    Returns:
        LLMClient 或 HiAgentClient 实例,两者都有 call_json 方法。

    Raises:
        ValueError: llm_backend 值不在支持的范围内,或缺少必要配置字段。
    """
    backend = config.get("llm_backend", "openai").strip().lower()

    if backend == "openai":
        base_url = config.get("llm_base_url", "")
        if not base_url:
            raise ValueError("llm_backend 为 openai 但 llm_base_url 未配置")
        return LLMClient(
            base_url=base_url,
            api_key=config.get("llm_api_key", ""),
            model=config.get("llm_model_name", ""),
            timeout=config.get("llm_timeout", 600),
        )

    if backend == "hiagent":
        base_url = config.get("hiagent_base_url", "")
        api_key = config.get("hiagent_api_key", "")
        if not base_url:
            raise ValueError("llm_backend 为 hiagent 但 hiagent_base_url 未配置")
        if not api_key:
            raise ValueError("llm_backend 为 hiagent 但 hiagent_api_key 未配置")
        return HiAgentClient(
            base_url=base_url,
            api_key=api_key,
            user_id=config.get("hiagent_user_id", "batch-runner"),
            timeout=config.get("llm_timeout", 600),
        )

    raise ValueError(
        f"不支持的 llm_backend 值: {backend!r}(支持 openai / hiagent）"
    )
