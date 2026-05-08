"""HiAgent 智能体调用封装

把 HiAgent 智能体平台的 HTTP API 包装成和 LLMClient 相同的 call_json 接口,
让任务侧不需要关心底层是直连大模型还是走智能体代理。

HiAgent API 的调用流程:
1. POST /create_conversation — 创建会话,拿到 AppConversationID
2. POST /chat_query_v2 — 发消息(blocking 模式),等完整回复
3. 从响应的 answer 字段取文本,用 extract_first_json 解析 JSON

和 LLMClient 的差异:
- temperature / max_tokens 等参数在 HiAgent 智能体配置侧设定,调用时不传
- 没有 response_format 约束,依赖 prompt 里的 schema 说明 + extract_first_json 兜底
- 每次调用新建会话,不复用(避免多轮上下文污染)

典型用法:
    from shared.hiagent_client import HiAgentClient

    client = HiAgentClient(
        base_url="http://x.x.x.x:port/api/proxy/api/v1",
        api_key="your-api-key",
        user_id="batch-runner",
    )
    result = client.call_json(prompt, schema)
"""
import json
from typing import Optional

import requests

from .llm_client import (
    LLMError,
    LLMEmptyResponseError,
    LLMJSONParseError,
    extract_first_json,
)


class HiAgentError(LLMError):
    """HiAgent API 调用错误(网络、鉴权、会话创建等)"""


class HiAgentClient:
    """HiAgent 智能体调用客户端。

    一个任务里创建一个实例,复用 base_url / api_key / user_id,
    多次调用 call_json() 处理不同输入。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        user_id: str = "batch-runner",
        timeout: int = 600,
    ):
        """
        Args:
            base_url: HiAgent API 基地址,到 /api/proxy/api/v1 这一级。
                例如 "http://x.x.x.x:port/api/proxy/api/v1"。
            api_key: HiAgent 的 ApiKey(同时用于 header 鉴权和请求体)。
            user_id: 用户标识,HiAgent 要求 1-20 字符,用于检索和统计。
            timeout: 单次请求超时秒数。blocking 模式下要等完整回复,
                建议和 LLMClient 保持一致(默认 600)。
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._user_id = user_id
        self._timeout = timeout

    def _headers(self) -> dict:
        return {
            "Apikey": self._api_key,
            "Content-Type": "application/json",
        }

    def _create_conversation(self) -> str:
        """创建新会话,返回 AppConversationID。

        Raises:
            HiAgentError: 创建失败(网络、鉴权、响应格式异常)。
        """
        url = f"{self._base_url}/create_conversation"
        body = {"UserID": self._user_id}

        try:
            resp = requests.post(
                url,
                headers=self._headers(),
                data=json.dumps(body),
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise HiAgentError(f"创建会话失败: {e}") from e

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise HiAgentError(f"创建会话响应解析失败: {e}") from e

        # 响应结构: {"Conversation": {"AppConversationID": "xxx", ...}}
        try:
            conv_id = data["Conversation"]["AppConversationID"]
        except (KeyError, TypeError) as e:
            raise HiAgentError(
                f"创建会话响应缺少 AppConversationID: {data}"
            ) from e

        if not conv_id:
            raise HiAgentError(f"创建会话返回空 ID: {data}")

        return conv_id

    def _chat_blocking(self, conversation_id: str, query: str) -> str:
        """以 blocking 模式发消息,返回完整的 answer 文本。

        Args:
            conversation_id: 会话 ID。
            query: 用户消息(即完整 prompt)。

        Returns:
            智能体回复的原始文本。

        Raises:
            HiAgentError: 请求失败或响应格式异常。
            LLMEmptyResponseError: 回复为空。
        """
        url = f"{self._base_url}/chat_query_v2"
        body = {
            "UserID": self._user_id,
            "AppConversationID": conversation_id,
            "Query": query,
            "ResponseMode": "blocking",
        }

        try:
            resp = requests.post(
                url,
                headers=self._headers(),
                data=json.dumps(body),
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise HiAgentError(f"对话请求失败: {e}") from e

        # V2 blocking 模式直接返回 JSON(不是 SSE)
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise HiAgentError(f"对话响应解析失败: {e}") from e

        # 检查是否有失败事件
        event = data.get("event", "")
        if event == "message_failed":
            raise HiAgentError(f"智能体返回失败: {data}")

        answer = data.get("answer", "")
        if not answer or not answer.strip():
            raise LLMEmptyResponseError("智能体回复为空")

        return answer

    def call_json(
        self,
        prompt: str,
        schema: dict,
        *,
        schema_name: str = "response",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        extra_body: Optional[dict] = None,
    ) -> dict:
        """单次调用,返回解析后的 JSON dict。

        接口签名和 LLMClient.call_json 保持一致,但 temperature /
        max_tokens / extra_body / schema_name 参数在 HiAgent 侧不生效,
        仅为了调用方代码兼容而保留(调用方不需要判断是哪个 client)。

        实际的 temperature / max_tokens 在 HiAgent 智能体配置里设定。

        Args:
            prompt: 完整的用户消息内容。
            schema: JSON schema 字典(HiAgent 侧无 response_format 约束,
                靠 prompt 里的 schema 说明引导输出)。
            schema_name: 不生效,仅兼容签名。
            temperature: 不生效,仅兼容签名。
            max_tokens: 不生效,仅兼容签名。
            extra_body: 不生效,仅兼容签名。

        Returns:
            解析后的 dict。

        Raises:
            HiAgentError: 会话创建或对话请求失败。
            LLMEmptyResponseError: 智能体回复为空。
            LLMJSONParseError: 回复内容无法解析为 JSON。
        """
        # 1. 每次调用新建会话,避免多轮上下文污染
        conversation_id = self._create_conversation()

        # 2. blocking 模式发消息,等完整回复
        answer = self._chat_blocking(conversation_id, prompt)

        # 3. 从回复文本中提取 JSON
        cleaned = extract_first_json(answer)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LLMJSONParseError(f"JSON 解析失败: {e}") from e
