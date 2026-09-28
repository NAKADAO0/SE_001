"""
核心两阶段分析流水线 (Two-Phase Code Pipeline)
企业级智能代码多阶段协同编排设计。

架构流程：
Phase 1: 零 LLM 共享特征抽取与 AST 规则初筛 (RuleEngine)
Phase 2: 垂直领域专家 Agent 并行/定向推理 (Agents: Reviewer / Tester / Refactor / Explainer)
Phase 3: 校验去重与最终统一呈现 (Verifier & Dedup)
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable
from ..core.config import Config
from ..core.llm_client import LLMClient
from ..schemas.code_types import ReviewReport, RiskSeverity
from .rule_engine import RuleEngine
from .verifier import Verifier
from ..agents.reviewer_agent import CodeReviewerAgent
from ..agents.explainer_agent import CodeExplainerAgent
from ..agents.tester_agent import TestGeneratorAgent
from ..agents.refactor_agent import CodeRefactorAgent


class CodePipeline:
    """两阶段多 Agent 代码分析流水线编排器"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.llm = LLMClient(self.config)
        self.rule_engine = RuleEngine()
        self.verifier = Verifier()

        # 挂载各垂直领域专家智能体
        self.reviewer_agent = CodeReviewerAgent(config=self.config, llm=self.llm)
        self.explainer_agent = CodeExplainerAgent(config=self.config, llm=self.llm)
        self.tester_agent = TestGeneratorAgent(config=self.config, llm=self.llm)
        self.refactor_agent = CodeRefactorAgent(config=self.config, llm=self.llm)

    def run_pipeline(
        self,
        target: str,
        task_type: str = "review",
        on_step: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        运行完整流水线
        :param target: 代码字符串或代码文件路径
        :param task_type: "review" | "explain" | "test" | "refactor"
        :param on_step: 观察者回调
        """
        def notify(event: str, data: Dict[str, Any]):
            if on_step:
                try:
                    on_step(event, data)
                except Exception:
                    pass

        # 1. 规范化获取源代码
        file_path_str = None
        code_content = target

        p = Path(target)
        if p.exists() and p.is_file():
            file_path_str = str(p)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    code_content = f.read()
            except Exception as e:
                return {
                    "success": False,
                    "error": f"无法读取目标文件: {str(e)}",
                }

        notify("pipeline_start", {
            "task_type": task_type,
            "target": file_path_str or "内存代码片段",
            "lines": len(code_content.splitlines()),
        })

        # ================= Phase 1: 静态规则引擎初筛 (零 LLM) =================
        phase1_result = self.rule_engine.analyze_source(code_content)
        notify("phase1_complete", {
            "syntax_valid": phase1_result["syntax_valid"],
            "functions": phase1_result["functions"],
            "classes": phase1_result["classes"],
            "initial_issues_count": len(phase1_result["issues"]),
        })

        # ================= Phase 2: 专业领域 Agent 深度推理 =================
        context_hint = ""
        if file_path_str:
            context_hint = f"目标文件路径: {file_path_str}\n"

        if phase1_result["issues"]:
            smell_texts = [f"行 {i.line}: {i.description}" for i in phase1_result["issues"]]
            context_hint += f"【Phase 1 静态初筛发现的线索】:\n" + "\n".join(smell_texts) + "\n"

        agent_output = ""
        selected_agent = None

        if task_type == "review":
            selected_agent = self.reviewer_agent
            prompt = (
                f"{context_hint}请深度审查以下代码，发现所有潜在 Bug、异常崩溃点与代码风险隐患，"
                f"并给出修复后的对比代码：\n\n```python\n{code_content}\n```"
            )
        elif task_type == "test":
            selected_agent = self.tester_agent
            prompt = (
                f"{context_hint}请为以下代码编写高覆盖率的 pytest 单元测试，"
                f"并主动调用 execute_python_code 工具在沙箱中运行验证，确保测试全部通过：\n\n```python\n{code_content}\n```"
            )
        elif task_type == "refactor":
            selected_agent = self.refactor_agent
            prompt = (
                f"{context_hint}请对以下代码进行架构重构，消除风险隐患（除零隐患、句柄泄露、硬编码if-elif等），应用合适设计模式（如策略模式、上下文管理器）。\n"
                f"【极其重要的要求】：请在重构设计说明后，必须在回答的最末尾使用独立的 ```python 代码块输出【整份完整的重构后 Python 源码】（第一行写 # FULL_REFACTORED_CODE 注释）。必须包含原业务中的全部类与所有函数，保证可以直接替换原代码完整运行，严禁省略或局部替换！\n\n```python\n{code_content}\n```"
            )
        elif task_type == "explain":
            selected_agent = self.explainer_agent
            prompt = (
                f"{context_hint}请详细解释以下代码的执行流程、核心算法原理解析与时空复杂度：\n\n```python\n{code_content}\n```"
            )
        else:
            selected_agent = self.reviewer_agent
            prompt = f"请分析以下代码：\n\n```python\n{code_content}\n```"

        notify("phase2_dispatch", {"agent": selected_agent.name})
        agent_output = selected_agent.run(prompt, on_step=on_step)

        # ================= Phase 3: 聚合与校验 (Verifier) =================
        final_issues = self.verifier.dedup_and_sort(phase1_result["issues"])
        notify("pipeline_finish", {"task_type": task_type, "status": "success"})

        return {
            "success": True,
            "task_type": task_type,
            "target": file_path_str or "inline_code",
            "phase1": {
                "syntax_valid": phase1_result["syntax_valid"],
                "functions": phase1_result["functions"],
                "classes": phase1_result["classes"],
                "rule_issues": [i.model_dump() for i in final_issues],
            },
            "phase2": {
                "agent_name": selected_agent.name,
                "report": agent_output,
            },
        }
