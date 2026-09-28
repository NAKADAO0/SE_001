"""
LLM 客户端封装模块：基于主流 Agent 框架 LangChain (langchain-openai) 实现底层驱动。
适配 DeepSeek API，集成指数退避重试与结果标准化。
"""

import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import (
        BaseMessage,
        HumanMessage,
        AIMessage,
        SystemMessage,
        ToolMessage,
    )
except ImportError:
    pass

from .config import Config


@dataclass
class LLMResponse:
    """标准化的 LLM 响应封装"""
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw_message: Optional[Any] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMClient:
    """基于 LangChain 的 LLM 统一客户端（适配 DeepSeek / OpenAI）"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.chat_model = ChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key or "sk-placeholder",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            temperature=self.config.temperature,
            max_retries=3,
        )

    def get_chat_model(self) -> ChatOpenAI:
        """获取底层原生 LangChain ChatOpenAI 实例"""
        return self.chat_model

    @staticmethod
    def _convert_messages(messages: List[Union[Dict[str, Any], BaseMessage]]) -> List[BaseMessage]:
        lc_msgs: List[BaseMessage] = []
        for m in messages:
            if isinstance(m, BaseMessage):
                lc_msgs.append(m)
                continue

            role = m.get("role")
            content = m.get("content", "") or ""

            if role == "system":
                lc_msgs.append(SystemMessage(content=content))
            elif role == "user":
                lc_msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                tc_raw = m.get("tool_calls")
                if tc_raw:
                    formatted_tcs = []
                    for tc in tc_raw:
                        if "function" in tc:
                            fn = tc["function"]
                            args = fn.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args) if args.strip() else {}
                                except Exception:
                                    args = {}
                            formatted_tcs.append({
                                "name": fn.get("name", ""),
                                "args": args,
                                "id": tc.get("id", ""),
                            })
                        elif "name" in tc and "args" in tc:
                            formatted_tcs.append(tc)
                    lc_msgs.append(AIMessage(content=content, tool_calls=formatted_tcs))
                else:
                    lc_msgs.append(AIMessage(content=content))
            elif role == "tool":
                lc_msgs.append(ToolMessage(
                    content=content,
                    tool_call_id=m.get("tool_call_id", ""),
                    name=m.get("name", ""),
                ))
        return lc_msgs

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        reraise=True,
    )
    def chat(
        self,
        messages: List[Union[Dict[str, Any], BaseMessage]],
        tools: Optional[List[Any]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """基于 LangChain 的对话推理"""
        temp = temperature if temperature is not None else self.config.temperature
        model = self.chat_model
        if temp != self.config.temperature:
            model = self.chat_model.copy(update={"temperature": temp})

        lc_messages = self._convert_messages(messages)

        if tools:
            runnable = model.bind_tools(tools)
        else:
            runnable = model

        ai_msg = runnable.invoke(lc_messages)
        content = str(ai_msg.content or "")
        standardized_tool_calls: List[Dict[str, Any]] = []

        raw_tool_calls = getattr(ai_msg, "tool_calls", None) or []
        for tc in raw_tool_calls:
            call_id = tc.get("id") or f"call_{tc.get('name', 'tool')}"
            fn_name = tc.get("name", "")
            fn_args = tc.get("args", {})
            fn_args_str = json.dumps(fn_args, ensure_ascii=False) if isinstance(fn_args, dict) else str(fn_args)

            standardized_tool_calls.append({
                "id": call_id,
                "type": "function",
                "function": {
                    "name": fn_name,
                    "arguments": fn_args_str,
                },
            })

        return LLMResponse(
            content=content,
            tool_calls=standardized_tool_calls,
            raw_message=ai_msg,
        )
