import pytest
from unittest.mock import MagicMock
from codemate.config import Config
from codemate.memory import ConversationMemory
from codemate.tools.registry import ToolRegistry, tool
from codemate.agent import CodeMateAgent


class MockLLMResponse:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


def test_agent_direct_response():
    """测试不需要工具调用的直接问答"""
    cfg = Config(api_key="mock-key")
    agent = CodeMateAgent(config=cfg)

    # Mock LLM 客户端直接返回文本
    mock_resp = MockLLMResponse(content="Python 中使用 def 定义函数。")
    agent.llm.chat = MagicMock(return_value=mock_resp)

    reply = agent.run("如何定义函数？")
    assert "def" in reply
    assert agent.llm.chat.call_count == 1
    # 记忆中应该记录了 1 条用户消息和 1 条助理消息
    messages = agent.memory.get_messages()
    assert messages[1]["content"] == "如何定义函数？"
    assert messages[2]["content"] == "Python 中使用 def 定义函数。"


def test_agent_tool_calling_loop():
    """测试 Agent 循环：输入 -> 决策调用工具 -> 执行工具并反馈 -> 输出最终结论"""
    registry = ToolRegistry()

    @tool(description="加法运算")
    def calculate_add(a: int, b: int) -> int:
        return a + b

    registry.register(calculate_add)

    cfg = Config(api_key="mock-key")
    agent = CodeMateAgent(config=cfg, tool_registry=registry)

    # 模拟第 1 轮返回 tool_calls，第 2 轮拿到结果返回最终答复
    tool_call_obj = {
        "id": "call_abc",
        "type": "function",
        "function": {"name": "calculate_add", "arguments": '{"a": 20, "b": 22}'},
    }
    resp1 = MockLLMResponse(content="", tool_calls=[tool_call_obj])
    resp2 = MockLLMResponse(content="计算结果是 42。")

    agent.llm.chat = MagicMock(side_effect=[resp1, resp2])

    reply = agent.run("请帮我计算 20 加 22")
    assert "42" in reply
    assert agent.llm.chat.call_count == 2


def test_agent_max_iterations_protection():
    """测试防止无限工具调用的迭代上限熔断保护"""
    cfg = Config(api_key="mock-key", max_iterations=2)
    agent = CodeMateAgent(config=cfg)

    # 模拟持续返回工具调用
    infinite_tool_call = {
        "id": "call_loop",
        "type": "function",
        "function": {"name": "non_existent_tool", "arguments": "{}"},
    }
    agent.llm.chat = MagicMock(
        return_value=MockLLMResponse(content="", tool_calls=[infinite_tool_call])
    )

    reply = agent.run("无限循环触发")
    assert "上限" in reply or "达到" in reply
