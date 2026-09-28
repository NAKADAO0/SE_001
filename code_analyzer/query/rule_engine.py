"""
静态规则引擎 (RuleEngine)：通过 AST 遍历与特征扫描进行零 LLM 的 Phase 1 快速代码分析。
"""

import ast
from typing import Dict, Any, List
from ..schemas.code_types import CodeSmellItem, RiskSeverity


class ASTAnalysisVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.smells: List[CodeSmellItem] = []
        self.has_zero_division_risk = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node.name)
        num_args = len(node.args.args)
        if num_args > 6:
            self.smells.append(CodeSmellItem(
                line=node.lineno,
                category="参数过多 (Long Parameter List)",
                severity=RiskSeverity.MEDIUM,
                description=f"函数 '{node.name}' 拥有 {num_args} 个形参，严重超出可维护性推荐阈值(6个)。",
                suggestion="重构为参数对象 (Parameter Object) 或使用 dataclass 统一封装。",
            ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self.smells.append(CodeSmellItem(
                line=node.lineno,
                category="裸 except 异常吞噬 (Bare Except)",
                severity=RiskSeverity.HIGH,
                description="发现不带任何异常类型的裸 except: 语句，它会无差别吞噬键盘中断(KeyboardInterrupt)与致命系统退出。",
                suggestion="指定具体异常类型，如 except ValueError: 或捕获后记录日志。",
            ))
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.smells.append(CodeSmellItem(
                    line=node.lineno,
                    category="通用异常静默抑制 (Silent Exception)",
                    severity=RiskSeverity.HIGH,
                    description="捕获通用 Exception 并直接执行 pass，隐瞒了真实线上异常故障。",
                    suggestion="至少记录错误日志或抛出业务特定异常。",
                ))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            # 标记包含除法运算
            self.has_zero_division_risk = True
        self.generic_visit(node)


class RuleEngine:
    """静态规则分析引擎"""

    def analyze_source(self, code: str) -> Dict[str, Any]:
        """对代码进行 Phase 1 快速规则解析"""
        if not code or not code.strip():
            return {
                "syntax_valid": False,
                "error": "代码内容为空",
                "functions": [],
                "classes": [],
                "issues": [],
            }

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                "syntax_valid": False,
                "error": f"语法错误: 第 {e.lineno} 行, {e.msg}",
                "functions": [],
                "classes": [],
                "issues": [CodeSmellItem(
                    line=e.lineno,
                    category="语法错误 (SyntaxError)",
                    severity=RiskSeverity.CRITICAL,
                    description=str(e.msg),
                    suggestion="修正代码语法后重新解析。",
                )],
            }

        visitor = ASTAnalysisVisitor()
        visitor.visit(tree)

        return {
            "syntax_valid": True,
            "error": None,
            "functions": visitor.functions,
            "classes": visitor.classes,
            "issues": visitor.smells,
            "syntax_issues": visitor.smells,
            "has_division": visitor.has_zero_division_risk,
        }
