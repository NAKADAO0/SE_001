import pytest
from codemate.memory import ConversationMemory


def test_memory_add_and_retrieve():
    mem = ConversationMemory(system_prompt="你是一个代码助手")
    mem.add_user_message("你好")
    mem.add_assistant_message("你好！有什么代码问题我可以帮你？")

    messages = mem.get_messages()
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "assistant"


def test_memory_sliding_window():
    # 最大保留 4 条消息（包括系统提示）
    mem = ConversationMemory(system_prompt="系统提示", max_messages=4)
    mem.add_user_message("问1")
    mem.add_assistant_message("答1")
    mem.add_user_message("问2")
    mem.add_assistant_message("答2")
    mem.add_user_message("问3")
    mem.add_assistant_message("答3")

    messages = mem.get_messages()
    # 必须保留 system prompt
    assert messages[0]["role"] == "system"
    # 总条数不能超过 max_messages
    assert len(messages) <= 4
    # 最新的问答3必须在其中
    assert messages[-1]["content"] == "答3"


def test_memory_tool_call_sequence():
    mem = ConversationMemory()
    tool_call_item = {
        "id": "call_123",
        "type": "function",
        "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
    }
    mem.add_assistant_message(content="", tool_calls=[tool_call_item])
    mem.add_tool_result(tool_call_id="call_123", tool_name="read_file", content="file content")

    messages = mem.get_messages()
    assert len(messages) == 3  # system, assistant(tool_calls), tool
    assert messages[1]["tool_calls"][0]["id"] == "call_123"
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_call_id"] == "call_123"
    assert messages[2]["content"] == "file content"


def test_memory_clear():
    mem = ConversationMemory(system_prompt="初始提示")
    mem.add_user_message("内容")
    assert len(mem.get_messages()) == 2
    mem.clear()
    messages = mem.get_messages()
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
