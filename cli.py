"""
命令行终端交互程序 (Rich CLI)：提供高颜值的终端代码助手交互体验。
"""

import sys
import os

# 适配 Windows 控制台 UTF-8 输出，防止 Emoji 触发 GBK 编码异常
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt
from codemate.config import Config
from codemate.agent import CodeMateAgent
from codemate.prompts import MODE_PROMPTS


console = Console()


def print_banner(config: Config):
    """打印彩色启动横幅"""
    banner_text = (
        "[bold cyan]╔═══════════════════════════════════════════════════════════════╗[/bold cyan]\n"
        "[bold cyan]║[/bold cyan]      [bold green]🤖 CodeMate-Agent | 全能智能代码助手系统[/bold green]                [bold cyan]║[/bold cyan]\n"
        "[bold cyan]║[/bold cyan]   [yellow]ReAct 循环[/yellow] • [magenta]工具自主调度[/magenta] • [blue]多轮记忆追踪[/blue] • [red]执行自纠错[/red]       [bold cyan]║[/bold cyan]\n"
        "[bold cyan]╚═══════════════════════════════════════════════════════════════╝[/bold cyan]"
    )
    console.print(banner_text)
    
    key_status = (
        "[bold green]✔ 已配置[/bold green]"
        if config.has_valid_api_key()
        else "[bold red]✘ 未检测到有效的 API Key (请在 .env 中设置 DEEPSEEK_API_KEY)[/bold red]"
    )
    
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold yellow")
    info_table.add_column()
    info_table.add_row("目标模型:", f"[bold white]{config.model_name}[/bold white]")
    info_table.add_row("API 节点:", f"[cyan]{config.base_url}[/cyan]")
    info_table.add_row("凭证状态:", key_status)
    info_table.add_row("快捷命令:", "[dim]/mode <模式>, /tools, /clear, /help, /exit[/dim]")
    
    console.print(Panel(info_table, title="[bold]环境与运行信息[/bold]", border_style="blue"))


def show_tools(agent: CodeMateAgent):
    """显示已注册的工具清单"""
    table = Table(title="🛠️ 当前已注册的智能体工具集", border_style="cyan")
    table.add_column("工具名称", style="bold green")
    table.add_column("功能描述", style="white")
    table.add_column("核心参数", style="yellow")

    for schema in agent.tool_registry.get_tools_schema():
        fn = schema["function"]
        name = fn["name"]
        desc = fn["description"]
        params = list(fn.get("parameters", {}).get("properties", {}).keys())
        table.add_row(name, desc, ", ".join(params) if params else "无")

    console.print(table)


def show_help():
    """显示快捷指令帮助"""
    help_md = """
### 💡 快捷命令指南：
- `/mode <name>`：切换策略模式。可选模式：`general` (通用), `review` (审查), `generation` (生成), `explanation` (解释), `testing` (测试), `refactor` (重构)
- `/tools`：查看当前 Agent 可用的所有工程工具
- `/clear`：清空当前会话的上下文记忆
- `/help`：查看此帮助信息
- `/exit` 或 `quit`：退出程序

### 🎯 推荐演示输入：
1. `审查 samples/buggy_code.py 中的代码质量与安全隐患`
2. `请阅读 samples/math_utils.py 并解释其中的 is_prime 函数的算法原理与时间复杂度`
3. `为 samples/math_utils.py 自动编写 pytest 单元测试，并使用工具运行验证`
4. `写一个计算数组中两数之和等于目标值的 Python 函数，并自动执行验证测试`
"""
    console.print(Panel(Markdown(help_md), title="帮助指南", border_style="yellow"))


def make_step_callback():
    """构建用于终端高亮渲染 Agent 思考与工具调用的回调函数"""
    def on_step(event_type: str, data: Dict[str, Any]):
        if event_type == "call_tool":
            tool_name = data.get("tool")
            args = data.get("arguments")
            iteration = data.get("iteration")
            console.print(
                f"[bold yellow]⚡ [第 {iteration} 轮思考] 触发工具调用:[/bold yellow] "
                f"[bold magenta]{tool_name}[/bold magenta] "
                f"[dim](参数: {args})[/dim]"
            )
        elif event_type == "tool_result":
            tool_name = data.get("tool")
            is_success = data.get("success")
            output = data.get("output", "")
            status_text = "[bold green]成功[/bold green]" if is_success else "[bold red]异常[/bold red]"
            
            # 如果输出过长，适度折叠预览
            preview = output[:300] + ("\n... (更多输出已回填给智能体)" if len(output) > 300 else "")
            console.print(Panel(
                preview,
                title=f"工具反馈 [{tool_name}] - {status_text}",
                border_style="green" if is_success else "red",
                padding=(0, 1),
            ))
        elif event_type == "max_iterations":
            console.print("[bold red]⚠️ 达到单次交互最大思考迭代次数上限，熔断保护触发。[/bold red]")
    return on_step


def main():
    config = Config.from_env()
    print_banner(config)

    # 如果没有配置 Key，允许在终端即时输入
    if not config.has_valid_api_key():
        console.print("[yellow]提示：检测到未配置 API Key。你可直接在下方粘贴 DeepSeek API Key（或按回车跳过使用预置 Mock 演示）：[/yellow]")
        manual_key = Prompt.ask("请输入 DEEPSEEK_API_KEY", default="")
        if manual_key.strip():
            config.api_key = manual_key.strip()
            os.environ["DEEPSEEK_API_KEY"] = config.api_key

    agent = CodeMateAgent(config=config)
    on_step_cb = make_step_callback()

    console.print("\n[bold green]Ready! 请输入您的代码任务（输入 /help 查看指引，输入 /exit 退出）：[/bold green]\n")

    while True:
        try:
            user_input = Prompt.ask(f"[bold cyan][{agent.current_mode}] User[/bold cyan]").strip()
            if not user_input:
                continue

            # 命令匹配
            if user_input.lower() in ("/exit", "exit", "quit", ":q"):
                console.print("[bold cyan]感谢使用 CodeMate-Agent，再见！[/bold cyan]")
                break
            elif user_input.lower() == "/help":
                show_help()
                continue
            elif user_input.lower() == "/tools":
                show_tools(agent)
                continue
            elif user_input.lower() == "/clear":
                agent.reset()
                console.print("[bold green]✔ 上下文记忆已成功清空。[/bold green]")
                continue
            elif user_input.lower().startswith("/mode"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].lower() in MODE_PROMPTS:
                    new_mode = parts[1].lower()
                    agent.switch_mode(new_mode)
                    console.print(f"[bold green]✔ 工作模式已切换至：{new_mode}[/bold green]")
                else:
                    console.print(f"[red]无效模式名。支持模式：{list(MODE_PROMPTS.keys())}[/red]")
                continue

            # 执行 Agent 循环
            with console.status("[bold green]Agent 正在深度推理与执行...[/bold green]", spinner="dots"):
                answer = agent.run(user_input, on_step=on_step_cb)

            console.print("\n[bold blue]🤖 CodeMate-Agent 回复:[/bold blue]")
            console.print(Markdown(answer))
            console.print("-" * 60)

        except KeyboardInterrupt:
            console.print("\n[yellow]操作已被用户取消。[/yellow]")
        except Exception as e:
            console.print(f"\n[bold red]发生未预期错误: {str(e)}[/bold red]")


if __name__ == "__main__":
    main()
