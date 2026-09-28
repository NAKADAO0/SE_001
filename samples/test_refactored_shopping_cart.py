"""针对重构版 ShoppingCart 的回归测试，覆盖原缺陷场景。"""

from decimal import Decimal

import pytest

from refactored_shopping_cart import (
    EmptyCartError,
    InvalidItemError,
    ShoppingCart,
    batch_checkout_users,
)

TOL = Decimal("0.001")


class TestFixedBugs:
    def test_share_discount_empty_cart_no_zero_division(self):
        """原缺陷1：空购物车 SHARE_DISCOUNT 不再抛 ZeroDivisionError。"""
        cart = ShoppingCart("u1")
        with pytest.raises(EmptyCartError):
            cart.apply_coupon("SHARE_DISCOUNT")

    def test_most_expensive_item_empty_returns_none(self):
        """原缺陷2：空购物车不再抛 ValueError。"""
        cart = ShoppingCart("u2")
        assert cart.get_most_expensive_item() is None

    def test_add_item_rejects_negative_price(self):
        """原缺陷4：负价被拦截。"""
        cart = ShoppingCart("u3")
        with pytest.raises(InvalidItemError):
            cart.add_item("恶意商品", -100.0, 3)

    def test_add_item_rejects_non_positive_qty(self):
        cart = ShoppingCart("u4")
        with pytest.raises(InvalidItemError):
            cart.add_item("正常商品", 10.0, 0)

    def test_coupon_discount_never_negative(self):
        """原缺陷：折扣不得超过总额。"""
        cart = ShoppingCart("u5")
        cart.add_item("小商品", 10.0, 1)  # 10 元，MINUS50 当扣 50
        assert cart.apply_coupon("MINUS50") == Decimal("0.00")

    def test_batch_checkout_rejects_ratio_gt_1(self):
        """原缺陷5：discount_ratio > 1 被拦截而非产生负金额。"""
        cart = ShoppingCart("u6")
        cart.add_item("a", 100.0, 1)
        with pytest.raises(ValueError):
            batch_checkout_users({"u6": cart}, 1.5)

    def test_file_handle_closed_after_apply(self, tmp_path):
        """原缺陷3：日志句柄使用 with 自动关闭，可安全删除文件。"""
        log = tmp_path / "log.txt"
        cart = ShoppingCart("u7")
        cart.add_item("a", 100.0, 1)
        cart.apply_coupon("VIP90", log_path=str(log))
        assert log.exists()
        log.unlink()  # Windows 下句柄未关会失败，能删除即证明已释放
        assert not log.exists()


class TestBusinessLogic:
    def test_vip90_discount(self):
        cart = ShoppingCart("u8")
        cart.add_item("a", 100.0, 2)  # 200 -> 九折，扣 20
        assert cart.apply_coupon("VIP90") == Decimal("180.00")

    def test_share_discount_counts_distinct_lines(self):
        """SHARE_DISCOUNT 按商品行数取平均：2 行各 100 元 -> avg=100, 扣 50 -> 150。"""
        cart = ShoppingCart("u9")
        cart.add_item("a", 100.0, 1)
        cart.add_item("b", 100.0, 1)
        assert cart.apply_coupon("SHARE_DISCOUNT") == Decimal("150.00")

    def test_share_discount_single_line_with_qty(self):
        """边界语义：单行 qty=2 时按 1 行计，avg=200 -> 扣 100 -> 100（保留原语义，需业务确认）。"""
        cart = ShoppingCart("u9b")
        cart.add_item("a", 100.0, 2)
        assert cart.apply_coupon("SHARE_DISCOUNT") == Decimal("100.00")

    def test_unknown_coupon_no_discount(self):
        cart = ShoppingCart("u10")
        cart.add_item("a", 50.0, 1)
        assert cart.apply_coupon("NOT_EXIST") == Decimal("50.00")

    def test_decimal_accumulation_accuracy(self):
        """0.1 + 0.2 类浮点误差不应出现。"""
        cart = ShoppingCart("u11")
        cart.add_item("a", 0.1, 1)
        cart.add_item("b", 0.2, 1)
        assert cart.get_total_price() == Decimal("0.30")

    def test_most_expensive_item(self):
        cart = ShoppingCart("u12")
        cart.add_item("cheap", 10.0)
        cart.add_item("pricey", 99.0)
        item = cart.get_most_expensive_item()
        assert item is not None and item["name"] == "pricey"

    def test_batch_checkout_valid(self):
        carts = {}
        for i in range(3):
            c = ShoppingCart(f"u{i}")
            c.add_item("a", 100.0, 1)
            carts[f"u{i}"] = c
        res = batch_checkout_users(carts, 0.1)
        assert all(v == Decimal("90.00") for v in res.values())
