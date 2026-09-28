"""
测试样例代码：电商购物车与结算模块 (ShoppingCart & Checkout)
供 CodeMate-Agent 进行全面的代码审查 (Review)、逻辑解释 (Explain)、
单元测试生成 (Test Generation) 与架构重构 (Refactor) 测试。
"""

import json
import time


class ShoppingCart:
    """购物车类：包含若干业务逻辑缺陷与风险隐患"""

    def __init__(self, user_id):
        self.user_id = user_id
        self.items = []  # 每个元素为 {"name": str, "price": float, "qty": int}

    def add_item(self, name, price, qty=1):
        """添加商品：未校验负数价格与数量"""
        self.items.append({"name": name, "price": price, "qty": qty})

    def get_total_price(self):
        """计算总价：存在浮点数累加与空列表处理"""
        total = 0.0
        for item in self.items:
            total += item["price"] * item["qty"]
        return total

    def apply_coupon(self, coupon_code):
        """
        计算优惠券折扣：
        缺陷 1: 缺少边界防御，除以 item 总数可能导致 ZeroDivisionError
        缺陷 2: 硬编码折扣逻辑，高耦合
        缺陷 3: 未关闭文件句柄，导致资源泄漏
        """
        total = self.get_total_price()
        discount = 0.0

        if coupon_code == "VIP90":
            discount = total * 0.1  # 九折
        elif coupon_code == "MINUS50":
            discount = 50.0
            if discount > total:
                # 缺陷：优惠大于总额时可能导致负支付金额
                discount = total
        elif coupon_code == "SHARE_DISCOUNT":
            # 严重Bug：空购物车时 len(self.items) 为 0，触发 ZeroDivisionError！
            avg_per_item = total / len(self.items)
            discount = avg_per_item * 0.5
        else:
            discount = 0.0

        # 缺陷：不安全的文件写入，未用 with 语句
        f = open("coupon_access_log.txt", "a")
        f.write(f"User {self.user_id} applied {coupon_code} at {time.time()}\n")
        # 缺少 f.close()

        final_price = total - discount
        return round(final_price, 2)

    def get_most_expensive_item(self):
        """
        获取单价最高的商品：
        严重Bug：若购物车为空，调用 max 抛出 ValueError: max() arg is an empty sequence
        """
        return max(self.items, key=lambda x: x["price"])


def batch_checkout_users(user_carts, discount_ratio):
    """
    批量结算函数：
    代码风险：嵌套过深，裸 except 吞没致命异常
    """
    results = {}
    for uid, cart in user_carts.items():
        try:
            total = cart.get_total_price()
            # 潜在逻辑错误：discount_ratio 若大于 1.0 未做拦截
            res = total * (1.0 - discount_ratio)
            results[uid] = round(res, 2)
        except:
            # 风险隐患：捕获所有异常并静默设为 0
            results[uid] = 0.0
    return results
