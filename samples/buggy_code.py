"""
演示样例 1：包含典型缺陷、代码风险与潜在运行异常的代码片段。
供 CodeMate-Agent 进行代码审查 (Review)、风险隐患诊断与重构 (Refactor) 演示。
"""

import os


def process_user_data(user_id, name, age, email, address, phone, score, tags, is_admin=False):
    """
    此函数存在多项风险隐患与缺陷：
    1. 参数过多（超过 6 个）
    2. 潜在 ZeroDivisionError 未做分母校验
    3. 裸 except 吞掉异常
    4. 资源打开未关闭（无 with 上下文）
    5. 类型转换无异常防范
    """
    print("Processing user: " + str(user_id))

    # 缺陷 1：潜在除零错误
    avg_score = score / age

    # 缺陷 2：危险的文件写入与资源泄露
    f = open("user_log.txt", "a")
    f.write(f"User {name}: avg score is {avg_score}\n")
    # 忘记 f.close()

    # 缺陷 3：空 except 吞噬所有异常
    try:
        user_num = int(user_id)
    except:
        pass

    return {
        "id": user_id,
        "name": name,
        "avg": avg_score,
    }


def calculate_discount(price, discount_rate):
    """计算折扣价格：缺乏负数与边界校验"""
    if discount_rate > 1.0:
        # 逻辑错误：折扣大于1应该报错或处理，这里却直接返回负数
        return price * (1 - discount_rate)
    return price * (1 - discount_rate)
