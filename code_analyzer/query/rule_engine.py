"""
静态规则引擎 (RuleEngine)：通过 AST 遍历与特征扫描进行零 LLM 的 Phase 1 快速代码分析。
全面覆盖：除零崩溃、资源未释放、空序列越界、异常静默吞噬、可变默认参数与架构坏味道。
"""

import ast
from typing import Dict, Any, List, Optional
from ..schemas.code_types import CodeSmellItem, RiskSeverity


class ASTAnalysisVisitor(ast.NodeVisitor):
    def __init__(self, code_lines: Optional[List[str]] = None):
        self.code_lines: List[str] = code_lines or []
        self.functions: List[str] = []
        self.classes: List[str] = []
        self.smells: List[CodeSmellItem] = []
        self.has_zero_division_risk = False
        self._with_open_lines = set()

    def _get_snippet(self, lineno: Optional[int]) -> Optional[str]:
        if lineno is not None and 1 <= lineno <= len(self.code_lines):
            return self.code_lines[lineno - 1].strip()
        return None

    def visit_With(self, node: ast.With):
        # 记录 with 语句中被安全管理的 open 调用行号
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func = item.context_expr.func
                if isinstance(func, ast.Name) and func.id == "open":
                    self._with_open_lines.add(getattr(item.context_expr, "lineno", node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node.name)
        num_args = len(node.args.args)
        if num_args > 6:
            self.smells.append(CodeSmellItem(
                line=node.lineno,
                category="参数过多 (Long Parameter List)",
                severity=RiskSeverity.MEDIUM,
                description=f"函数 '{node.name}' 拥有 {num_args} 个形参，超出可维护性推荐阈值(6个)。",
                suggestion="重构为参数对象 (Parameter Object) 或使用 dataclass 统一封装。",
                snippet=self._get_snippet(node.lineno),
                fix_code=f"@dataclass\nclass {node.name.capitalize()}Params:\n    ...",
            ))

        # 检查可变默认形参 (Mutable Default Argument)
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.smells.append(CodeSmellItem(
                    line=default.lineno if hasattr(default, "lineno") else node.lineno,
                    category="⚙️ 可变默认参数陷阱 (Mutable Default)",
                    severity=RiskSeverity.MEDIUM,
                    description=f"函数 '{node.name}' 使用了可变容器作为默认参数值，跨调用时将产生全局副作用和数据污染。",
                    suggestion="建议将默认值设为 None，并在函数体内做动态判断赋值。",
                    snippet=self._get_snippet(node.lineno),
                    fix_code="def func(param=None):\n    if param is None:\n        param = []",
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
                snippet=self._get_snippet(node.lineno),
                fix_code="except Exception as e:\n    logger.error(f'Operation failed: {e}')\n    raise",
            ))
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.smells.append(CodeSmellItem(
                    line=node.lineno,
                    category="通用异常静默抑制 (Silent Exception)",
                    severity=RiskSeverity.HIGH,
                    description="捕获通用 Exception 并直接执行 pass，隐瞒了真实线上异常故障。",
                    suggestion="至少记录错误日志或抛出业务特定异常，切勿静默吞噬。",
                    snippet=self._get_snippet(node.lineno),
                    fix_code="except Exception as e:\n    logger.warning(f'Handled exception: {e}')",
                ))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            self.has_zero_division_risk = True
            # 检测分母是否为动态变量或 len(...) 计算
            denom = node.right
            is_risky_denom = False
            denom_desc = "动态分母"

            if isinstance(denom, ast.Call) and isinstance(denom.func, ast.Name) and denom.func.id == "len":
                is_risky_denom = True
                denom_desc = "容器长度 len(...)"
            elif isinstance(denom, ast.Name):
                is_risky_denom = True
                denom_desc = f"变量 '{denom.id}'"

            if is_risky_denom:
                self.smells.append(CodeSmellItem(
                    line=node.lineno,
                    category="➗ 除零致命风险 (ZeroDivisionError)",
                    severity=RiskSeverity.CRITICAL,
                    description=f"检测到除法/取模运算使用 {denom_desc} 作为除数，未做判空或零值前置防御，当输入空序列或0时将触发致命崩溃。",
                    suggestion="执行除法前必须做边界校验，例如 `if not items: return 0.0` 或判断除数大于0。",
                    snippet=self._get_snippet(node.lineno),
                    fix_code="if not items:\n    return 0.0\nreturn total / len(items)",
                ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. 检测裸 open(...) 句柄未安全关闭
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.lineno not in self._with_open_lines:
                self.smells.append(CodeSmellItem(
                    line=node.lineno,
                    category="📂 资源句柄未安全释放 (Resource Leak)",
                    severity=RiskSeverity.HIGH,
                    description="使用裸 open() 打开文件未置于 with 上下文管理器中，发生异常或并发运行时将导致操作系统文件句柄持续泄露。",
                    suggestion="请使用 `with open(...) as f:` 语法糖进行自动资源生命周期管理。",
                    snippet=self._get_snippet(node.lineno),
                    fix_code="with open('access.log', 'a', encoding='utf-8') as f:\n    f.write(log_entry)",
                ))

        # 2. 检测空序列直接调用 max() / min() 崩溃风险
        elif isinstance(node.func, ast.Name) and node.func.id in ("max", "min"):
            # 如果只有一个参数且未提供 default 关键字参数
            has_default = any(kw.arg == "default" for kw in node.keywords)
            if len(node.args) == 1 and not has_default:
                self.smells.append(CodeSmellItem(
                    line=node.lineno,
                    category="🔍 空序列崩溃风险 (Empty Sequence Error)",
                    severity=RiskSeverity.CRITICAL,
                    description=f"对集合/列表调用 `{node.func.id}()` 且未提供 default 防御参数，若传入空序列将直接抛出 ValueError 运行时崩溃。",
                    suggestion=f"增加判空防御或传入 `default=None`，例如 `if not seq: return None`。",
                    snippet=self._get_snippet(node.lineno),
                    fix_code="if not items:\n    return None\nreturn max(items, key=lambda x: x.price)",
                ))

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

        code_lines = code.splitlines()

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
                    snippet=code_lines[e.lineno - 1] if e.lineno and e.lineno <= len(code_lines) else None,
                )],
            }

        visitor = ASTAnalysisVisitor(code_lines=code_lines)
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
