"""
演示样例 2：数学与算法基础工具模块。
供 CodeMate-Agent 进行代码解释 (Explain)、单元测试生成 (Test Generation) 与自动执行验证。
"""

from typing import List


def fibonacci(n: int) -> int:
    """计算第 n 项斐波那契数 (n >= 0)"""
    if n < 0:
        raise ValueError("n 不能为负数")
    if n in (0, 1):
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def is_prime(num: int) -> bool:
    """判断一个整数是否为素数"""
    if num <= 1:
        return False
    if num <= 3:
        return True
    if num % 2 == 0 or num % 3 == 0:
        return False
    i = 5
    while i * i <= num:
        if num % i == 0 or num % (i + 2) == 0:
            return False
        i += 6
    return True


def matrix_addition(mat_a: List[List[float]], mat_b: List[List[float]]) -> List[List[float]]:
    """两矩阵相加"""
    if not mat_a or not mat_b:
        raise ValueError("矩阵不能为空")
    rows = len(mat_a)
    cols = len(mat_a[0])
    if len(mat_b) != rows or any(len(row) != cols for row in mat_b):
        raise ValueError("两矩阵维度必须完全一致")

    result = []
    for r in range(rows):
        result_row = [mat_a[r][c] + mat_b[r][c] for c in range(cols)]
        result.append(result_row)
    return result
