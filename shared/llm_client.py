"""LLM 调用封装

把 OpenAI SDK 调用、JSON 提取兜底、常见错误检测收在一处,
让任务侧只需关注"传什么 prompt、要什么 schema",不用每个任务都写一遍。

典型用法:
    from shared.llm_client import LLMClient

    client = LLMClient(
        base_url="http://x.x.x.x:port/v1",
        api_key="not-needed",
        model="Qwen3.5-35B-A3B",
    )
    result = client.call_json(prompt, schema, schema_name="my_schema")
"""
import json
from typing import Optional

from openai import OpenAI


class LLMError(Exception):
    """LLM 调用相关错误的基类"""


class LLMTruncatedError(LLMError):
    """模型输出被截断(finish_reason == 'length',max_tokens 不够)"""


class LLMEmptyResponseError(LLMError):
    """模型返回空字符串"""


class LLMJSONParseError(LLMError):
    """模型返回的内容无法解析为 JSON"""


def extract_first_json(raw: str) -> str:
    """从字符串中提取第一个完整 JSON 对象。

    用于兜底处理模型偶尔在 JSON 前后夹带 markdown 代码块或解释文字的情况。
    严格按 { } 配对,字符串内的 { } 不计入。

    Args:
        raw: 原始字符串,可能含 markdown 包裹或前后说明文字。

    Returns:
        提取出的 JSON 字符串(从第一个 { 到匹配的 })。

    Raises:
        LLMJSONParseError: 找不到 JSON 起始标记或括号不匹配。
    """
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()

    start = s.find("{")
    if start == -1:
        raise LLMJSONParseError("未找到 JSON 起始标记")

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
    raise LLMJSONParseError("JSON 括号不匹配")


class LLMClient:
    """LLM 调用客户端。

    一个任务里通常只创建一个实例,复用 base_url / model / timeout 等配置,
    多次调用 call_json() 处理不同输入。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 600,
    ):
        """
        Args:
            base_url: OpenAI 兼容 API 的基地址。
            api_key: API key,本地部署没认证时传 "not-needed"。
            model: 模型名。
            timeout: 单次调用超时秒数。
        """
        self.model = model
        self._client = OpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=timeout,
        )

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
        """单次 LLM 调用,要求模型按 JSON schema 输出,返回解析后的 dict。

        Args:
            prompt: 完整的 user 消息内容。
            schema: JSON schema 字典,用于 response_format 约束。
            schema_name: schema 在 response_format 里的名字,符合 OpenAI 规范即可。
            temperature: 采样温度。
            max_tokens: 输出最大 token 数,设小了会被截断。
            extra_body: 给特定后端(如 vLLM/Qwen)传的额外参数,
                例如 {"chat_template_kwargs": {"enable_thinking": False}}。

        Returns:
            解析后的 dict。

        Raises:
            LLMTruncatedError: 输出被截断,需要增大 max_tokens。
            LLMEmptyResponseError: 模型返回空字符串。
            LLMJSONParseError: 返回内容无法解析为 JSON。
        """
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
            extra_body=extra_body,
        )

        if response.choices[0].finish_reason == "length":
            raise LLMTruncatedError("输出被截断,max_tokens 不够")

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise LLMEmptyResponseError("模型返回为空")

        cleaned = extract_first_json(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LLMJSONParseError(f"JSON 解析失败: {e}") from e
