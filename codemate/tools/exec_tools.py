"""
代码执行工具：提供进程级安全沙箱隔离运行 Python 代码与单元测试的能力。
"""

import sys
import subprocess
from typing import Dict, Any
from .registry import tool


@tool(name="execute_python_code", description="在隔离子进程中安全执行指定的 Python 代码，返回标准输出、标准错误和执行状态")
def execute_python_code(code: str, timeout: int = 15) -> Dict[str, Any]:
    """执行 Python 代码片段"""
    if not code or not code.strip():
        return {"success": False, "output": "执行失败：代码内容不能为空"}

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode == 0:
            output_msg = stdout if stdout else "代码执行成功，无标准输出。"
            return {
                "success": True,
                "output": output_msg,
                "returncode": 0,
            }
        else:
            err_msg = stderr if stderr else stdout
            return {
                "success": False,
                "output": f"代码执行报错 (退出码 {proc.returncode}):\n{err_msg}",
                "returncode": proc.returncode,
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": f"代码执行超时：超过了预设的 {timeout} 秒限制，已被系统强制终止（请检查是否存在死循环或无限阻塞）。",
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"执行器内部异常: {str(e)}",
        }


@tool(name="run_pytest", description="使用 pytest 执行指定的测试文件或测试目录，返回详细的测试通过与失败报告")
def run_pytest(test_path: str = "tests", timeout: int = 30) -> Dict[str, Any]:
    """运行 pytest 测试套件"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        output = (proc.stdout + "\n" + proc.stderr).strip()
        return {
            "success": proc.returncode == 0,
            "output": output,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": f"Pytest 执行超时 (超过 {timeout} 秒)。",
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"调用 pytest 失败: {str(e)}",
        }
