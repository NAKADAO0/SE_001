"""
LangChain 框架原生集成测试：验证底层驱动、消息协议与工具绑定的合规性。
"""

import pytest
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import StructuredTool

from code_analyzer.core.config import Config
from code_analyzer.core.llm_client import LLMClient
from code_analyzer.core.memory import ConversationMemory
from code_analyzer.tools import get_analyzer_tool_registry
from code_analyzer.agents.reviewer_agent import CodeReviewerAgent


def test_langchain_llm_client_initialization():
    """验证 LLMClient 基于 LangChain ChatOpenAI 实现"""
    cfg = Config(api_key="test-key", base_url="https://api.deepseek.com/v1", model_name="deepseek-flash")
    client = LLMClient(config=cfg)
    chat_model = client.get_chat_model()

    assert isinstance(chat_model, ChatOpenAI)
    assert chat_model.model_name == "deepseek-flash"
    assert chat_model.openai_api_base == "https://api.deepseek.com/v1"


def test_langchain_tool_conversion():
    """验证工具注册表能够生成标准的 LangChain StructuredTool"""
    registry = get_analyzer_tool_registry()
    lc_tools = registry.to_langchain_tools()

    assert len(lc_tools) >= 5
    tool_names = [t.name for t in lc_tools]
    assert "read_file" in tool_names
    assert "execute_python_code" in tool_names
    assert "run_pytest" in tool_names
    assert "lint_code" in tool_names

    for t in lc_tools:
        assert isinstance(t, StructuredTool)


def test_langchain_memory_conversion():
    """验证上下文记忆能够标准转换为 LangChain BaseMessage 序列"""
    memory = ConversationMemory(system_prompt="系统提示")
    memory.add_user_message("用户提问")
    memory.add_assistant_message(content="思考中", tool_calls=[{
        "id": "tc_1",
        "function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'}
    }])
    memory.add_tool_result("tc_1", "read_file", "print('hello')")
    memory.add_assistant_message(content="分析完毕")

    lc_msgs = memory.to_langchain_messages()
    assert len(lc_msgs) == 5
    assert isinstance(lc_msgs[0], SystemMessage)
    assert lc_msgs[0].content == "系统提示"
    assert isinstance(lc_msgs[1], HumanMessage)
    assert lc_msgs[1].content == "用户提问"
    assert isinstance(lc_msgs[2], AIMessage)
    assert len(lc_msgs[2].tool_calls) == 1
    assert lc_msgs[2].tool_calls[0]["name"] == "read_file"
    assert isinstance(lc_msgs[3], ToolMessage)
    assert lc_msgs[3].tool_call_id == "tc_1"
    assert isinstance(lc_msgs[4], AIMessage)
    assert lc_msgs[4].content == "分析完毕"


def test_reviewer_agent_uses_langchain():
    """验证专家 Agent 底层挂载 LangChain 工具与模型"""
    cfg = Config(api_key="test-key")
    agent = CodeReviewerAgent(config=cfg)
    assert len(agent.langchain_tools) >= 5
    for t in agent.langchain_tools:
        assert isinstance(t, StructuredTool)
