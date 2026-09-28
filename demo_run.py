"""
一键自动化端到端测试与演示脚本 (Demo Run)
直接运行：python demo_run.py
自动向 Agent 发送测试任务，演示其自主调用工具、分析代码、执行沙箱并返回报告的全过程。
"""

import sys
import os

# 适配 Windows 控制台输出编码
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from codemate.agent import CodeMateAgent
from codemate.config import Config


console = Console()


def main():
    config = Config.from_env()
    console.print(Panel(
        f"[bold green]🚀 CodeMate-Agent 自动化端到端演示[/bold green]\n"
        f"模型: [cyan]{config.model_name}[/cyan] | 节点: [cyan]{config.base_url}[/cyan]\n"
        f"测试目标: 自主读取并深度审查 [yellow]samples/demo_shopping_cart.py[/yellow]",
        border_style="cyan"
    ))

    agent = CodeMateAgent(mode="review", config=config)

    def on_step_callback(event_type: str, data: dict):
        if event_type == "call_tool":
            tool_name = data.get("tool")
            args = data.get("arguments")
            iteration = data.get("iteration")
            console.print(
                f"[yellow]⚡ [第 {iteration} 轮思考] 智能体自主调用工具:[/yellow] "
                f"[bold magenta]{tool_name}[/bold magenta] "
                f"[dim](参数: {args})[/dim]"
            )
        elif event_type == "tool_result":
            tool_name = data.get("tool")
            is_success = data.get("success")
            output = data.get("output", "")
            preview = output[:200] + ("\n... (更多输出已回传)" if len(output) > 200 else "")
            console.print(Panel(
                preview,
                title=f"工具反馈 [{tool_name}] - {'✅ 成功' if is_success else '❌ 报错'}",
                border_style="green" if is_success else "red",
                padding=(0, 1),
            ))

    task_prompt = (
        "请调用 read_file 工具读取 samples/demo_shopping_cart.py，"
        "并结合 lint_code 工具静态分析其结构与代码坏味道，"
        "指出其中的严重 Bug、潜在异常崩溃点，并给出规范的重构建议。"
    )

    console.print(f"\n[bold blue]🧑‍💻 用户输入指令:[/bold blue] {task_prompt}\n")

    with console.status("[bold green]Agent 正在调度工具与推理分析中...[/bold green]", spinner="dots"):
        result = agent.run(task_prompt, on_step=on_step_callback)

    console.print("\n[bold green]═════════════════ 🤖 CodeMate-Agent 审查与诊断报告 ═════════════════[/bold green]\n")
    console.print(Markdown(result))
    console.print("\n[bold green]✔ 端到端测试演示圆满完成！[/bold green]\n")


if __name__ == "__main__":
    main()
