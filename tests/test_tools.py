import os
import tempfile
import pytest
from codemate.tools.registry import ToolRegistry, tool
from codemate.tools.file_tools import read_file, write_file, list_directory
from codemate.tools.exec_tools import execute_python_code
from codemate.tools.analysis_tools import lint_code


def test_tool_decorator_and_schema():
    registry = ToolRegistry()

    @tool(description="计算两数之和")
    def add(a: int, b: int = 1) -> int:
        return a + b

    registry.register(add)
    schemas = registry.get_tools_schema()

    assert len(schemas) == 1
    tool_def = schemas[0]
    assert tool_def["type"] == "function"
    assert tool_def["function"]["name"] == "add"
    assert "a" in tool_def["function"]["parameters"]["properties"]
    assert "b" in tool_def["function"]["parameters"]["properties"]
    assert "a" in tool_def["function"]["parameters"]["required"]
    assert "b" not in tool_def["function"]["parameters"]["required"]

    # 测试工具执行
    result = registry.execute("add", {"a": 10, "b": 5})
    assert result["success"] is True
    assert result["output"] == 15


def test_file_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.py")
        content = "def hello():\n    return 'world'\n"
        
        # 写入
        w_res = write_file(path=test_file, content=content)
        assert w_res["success"] is True
        
        # 读取
        r_res = read_file(path=test_file)
        assert r_res["success"] is True
        assert "hello()" in r_res["output"]
        
        # 列出目录
        l_res = list_directory(path=tmpdir)
        assert l_res["success"] is True
        assert any("test.py" in item for item in l_res["output"])


def test_execute_python_code_success():
    code = "print('Hello from sandbox')\nprint(1 + 2)"
    res = execute_python_code(code=code)
    assert res["success"] is True
    assert "Hello from sandbox" in res["output"]
    assert "3" in res["output"]


def test_execute_python_code_error_capture():
    code = "1 / 0"
    res = execute_python_code(code=code)
    assert res["success"] is False
    assert "ZeroDivisionError" in res["output"]


def test_execute_python_code_timeout():
    code = "import time\ntime.sleep(5)"
    res = execute_python_code(code=code, timeout=1)
    assert res["success"] is False
    assert "超时" in res["output"]


def test_lint_code_analysis():
    # 正常代码 AST 检查
    valid_code = "def foo(x):\n    return x * 2\n"
    res = lint_code(code=valid_code)
    assert res["success"] is True
    assert "foo" in res["output"]

    # 语法错误代码
    invalid_code = "def foo(x\n    return"
    bad_res = lint_code(code=invalid_code)
    assert bad_res["success"] is False
    assert "SyntaxError" in bad_res["output"]
