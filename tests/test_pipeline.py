import pytest
from unittest.mock import MagicMock
from code_analyzer.query.rule_engine import RuleEngine
from code_analyzer.query.verifier import Verifier
from code_analyzer.schemas.code_types import CodeSmellItem, RiskSeverity
from code_analyzer.query.pipeline import CodePipeline
from codemate.llm import LLMResponse


def test_rule_engine_syntax_and_smells():
    engine = RuleEngine()
    
    # 正常代码含过多参数
    code = "def test_func(a, b, c, d, e, f, g):\n    return a\n"
    res = engine.analyze_source(code)
    assert res["syntax_valid"] is True
    assert "test_func" in res["functions"]
    assert any("参数过多" in item.category for item in res["issues"])

    # 包含除法运算
    div_code = "def calc(x, y):\n    return x / y\n"
    div_res = engine.analyze_source(div_code)
    assert div_res["has_division"] is True

    # 包含裸 except
    bare_code = "try:\n    x = 1\nexcept:\n    pass\n"
    bare_res = engine.analyze_source(bare_code)
    assert any("裸 except" in item.category for item in bare_res["issues"])


def test_verifier_dedup_and_sort():
    item1 = CodeSmellItem(line=10, category="参数过多", severity=RiskSeverity.MEDIUM, description="", suggestion="")
    item2 = CodeSmellItem(line=5, category="裸 except", severity=RiskSeverity.HIGH, description="", suggestion="")
    item3 = CodeSmellItem(line=10, category="参数过多", severity=RiskSeverity.MEDIUM, description="", suggestion="")  # 重复项
    
    res = Verifier.dedup_and_sort([item1, item2, item3])
    assert len(res) == 2
    # HIGH 风险排在前面
    assert res[0].severity == RiskSeverity.HIGH
    assert res[1].severity == RiskSeverity.MEDIUM


def test_code_pipeline_mock_run():
    pipeline = CodePipeline()
    # Mock Reviewer Agent LLM
    pipeline.reviewer_agent.llm.chat = MagicMock(
        return_value=LLMResponse(content="代码审查完成：无严重安全隐患。")
    )

    result = pipeline.run_pipeline(
        target="def hello():\n    return 'world'\n",
        task_type="review",
    )
    assert result["success"] is True
    assert "phase1" in result
    assert "phase2" in result
    assert result["phase1"]["syntax_valid"] is True
    assert "代码审查完成" in result["phase2"]["report"]


def test_parse_user_intent_and_prompt():
    from web_app import parse_user_intent_and_prompt
    
    # 1. 帮助触发
    task, prompt, is_help = parse_user_intent_and_prompt("/")
    assert is_help is True
    assert task == "help"

    task, prompt, is_help = parse_user_intent_and_prompt("/帮助")
    assert is_help is True

    # 2. 中文斜杠指令
    task, prompt, is_help = parse_user_intent_and_prompt("/审查")
    assert task == "review"
    assert is_help is False

    task, prompt, is_help = parse_user_intent_and_prompt("/重构 消除重复逻辑")
    assert task == "refactor"
    assert "消除重复逻辑" in prompt

    task, prompt, is_help = parse_user_intent_and_prompt("/测试")
    assert task == "test"

    task, prompt, is_help = parse_user_intent_and_prompt("/解释 评估复杂度")
    assert task == "explain"
    assert "评估复杂度" in prompt

    # 3. 自然语言意图智能识别
    task, prompt, is_help = parse_user_intent_and_prompt("帮我排查一下这块代码有没有除零崩溃风险")
    assert task == "review"

    task, prompt, is_help = parse_user_intent_and_prompt("重构一下这个函数，把嵌套循环改掉")
    assert task == "refactor"

    task, prompt, is_help = parse_user_intent_and_prompt("写几个单测跑一下 pytest")
    assert task == "test"

    task, prompt, is_help = parse_user_intent_and_prompt("这段代码的时间和空间复杂度是多少")
    assert task == "explain"
