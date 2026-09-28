"""
代码静态分析工具：利用 Python AST 语法树对代码进行语法合规性检查、结构剖析与基础代码异味检测。
"""

import ast
from pathlib import Path
from typing import Dict, Any, List
from .registry import tool


class CodeSmellVisitor(ast.NodeVisitor):
    """AST 访问器：检测基础代码异味"""

    def __init__(self):
        self.smells: List[str] = []
        self.functions: List[str] = []
        self.classes: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(f"函数 '{node.name}' (行号 {node.lineno})")
        # 参数过多检查
        num_args = len(node.args.args)
        if num_args > 6:
            self.smells.append(
                f"[行 {node.lineno}] 函数 '{node.name}' 参数过多 ({num_args} 个)，建议重构为参数对象或精简接口"
            )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.functions.append(f"异步函数 '{node.name}' (行号 {node.lineno})")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(f"类 '{node.name}' (行号 {node.lineno})")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # 裸捕获 except: 或 except Exception: pass 检查
        if node.type is None:
            self.smells.append(
                f"[行 {node.lineno}] 发现裸 except: 语句（未指定捕获类型），可能掩盖关键运行时崩溃"
            )
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.smells.append(
                    f"[行 {node.lineno}] 发现捕获通用异常并静默 pass，这是一种危险的抗模式 (Anti-pattern)"
                )
        self.generic_visit(node)


@tool(name="lint_code", description="静态分析 Python 代码的语法合法性，并解析函数、类定义及检测常见代码坏味道")
def lint_code(code: str = "", file_path: str = "") -> Dict[str, Any]:
    """静态语法分析"""
    target_code = code
    if file_path:
        p = Path(file_path)
        if not p.exists():
            return {"success": False, "output": f"文件不存在: {file_path}"}
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                target_code = f.read()
        except Exception as e:
            return {"success": False, "output": f"读取分析文件失败: {str(e)}"}

    if not target_code.strip():
        return {"success": False, "output": "分析内容为空"}

    try:
        tree = ast.parse(target_code)
    except SyntaxError as syn_err:
        return {
            "success": False,
            "output": f"Python 语法错误 (SyntaxError):\n"
                      f"第 {syn_err.lineno} 行，第 {syn_err.offset} 列\n"
                      f"代码片段: {syn_err.text.strip() if syn_err.text else 'N/A'}\n"
                      f"详情: {syn_err.msg}",
            "syntax_valid": False,
        }

    visitor = CodeSmellVisitor()
    visitor.visit(tree)

    report_lines = [
        "语法检查通过：AST 结构解析成功。",
        f"包含结构: {len(visitor.classes)} 个类, {len(visitor.functions)} 个函数。",
    ]
    if visitor.classes:
        report_lines.append(f"类列表: {', '.join(visitor.classes)}")
    if visitor.functions:
        report_lines.append(f"函数列表: {', '.join(visitor.functions)}")

    if visitor.smells:
        report_lines.append("\n发现潜在代码坏味道 / 优化建议:")
        for smell in visitor.smells:
            report_lines.append(f" - {smell}")
    else:
        report_lines.append("\n未发现明显的 AST 级别代码异味。")

    return {
        "success": True,
        "output": "\n".join(report_lines),
        "syntax_valid": True,
        "smells": visitor.smells,
    }
