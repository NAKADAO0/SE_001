"""重构版购物车模块的回归测试。

覆盖：
* 原缺陷修复（裸 except / ZeroDivisionError / 负支付 / 资源泄漏 / 空车 max）
* 设计模式收益（策略可插拔、注册表可注入 = 开闭原则 + 依赖倒置）
* 向后兼容（接口签名、返回类型、字典式下标访问）
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shopping_cart_refactored_final import (  # noqa: E402
    CartError,
    CartItem,
    Coupon,
    CouponRegistry,
    EmptyCartError,
    InvalidDiscountError,
    InvalidItemError,
    PercentageCoupon,
    ShoppingCart,
    batch_checkout_users,
    coupon_access_log,
)

from decimal import Decimal  # noqa: E402


# --------------------------------------------------------------------------- #
# 原缺陷修复
# --------------------------------------------------------------------------- #
class TestBugFixes:
    def test_share_discount_empty_cart_no_zero_division(self):
        """原：空车应用 SHARE_DISCOUNT -> ZeroDivisionError；改：业务异常。"""
        with pytest.raises(EmptyCartError):
            ShoppingCart("u").apply_coupon("SHARE_DISCOUNT")

    def test_empty_cart_most_expensive_raises_business_error(self):
        """原：max() 抛 ValueError；改：EmptyCartError（仍可被 except ValueError 捕获）。"""
        with pytest.raises(EmptyCartError):
            ShoppingCart("u").get_most_expensive_item()
        with pytest.raises(ValueError):  # 兼容旧捕获习惯
            ShoppingCart("u").get_most_expensive_item()

    def test_negative_price_and_qty_rejected(self):
        cart = ShoppingCart("u")
        with pytest.raises(InvalidItemError):
            cart.add_item("x", -1.0, 1)
        with pytest.raises(InvalidItemError):
            cart.add_item("x", 1.0, 0)
        assert cart.items == []

    def test_no_negative_payment_when_discount_exceeds_total(self):
        """MINUS50 立减 50，总价 30 -> 折后价应为 0 而非 -20。"""
        cart = ShoppingCart("u")
        cart.add_item("cheap", 30.0, 1)
        assert cart.apply_coupon("MINUS50") == 0.0

    def test_float_precision_with_decimal(self):
        cart = ShoppingCart("u")
        cart.add_item("a", 0.1, 1)
        cart.add_item("b", 0.2, 1)
        assert cart.get_total_price() == 0.3  # 而非 0.30000000000000004

    def test_unknown_coupon_is_no_discount(self):
        cart = ShoppingCart("u")
        cart.add_item("a", 100.0, 1)
        assert cart.apply_coupon("NOT_EXIST") == 100.0


# --------------------------------------------------------------------------- #
# 裸 except 修复：致命异常必须向上冒泡
# --------------------------------------------------------------------------- #
class TestBareExceptFixed:
    class _ExplodingCart(ShoppingCart):
        def get_total_price(self) -> float:
            raise KeyboardInterrupt

    class _BadCart(ShoppingCart):
        def get_total_price(self) -> float:
            raise CartError("boom")

    def test_keyboard_interrupt_not_swallowed(self):
        with pytest.raises(KeyboardInterrupt):
            batch_checkout_users({"u1": self._ExplodingCart("u1")}, 0.1)

    def test_system_exit_not_swallowed(self):
        class _ExitCart(ShoppingCart):
            def get_total_price(self) -> float:
                raise SystemExit(1)

        with pytest.raises(SystemExit):
            batch_checkout_users({"u1": _ExitCart("u1")}, 0.1)

    def test_business_error_isolated_per_user(self):
        good = ShoppingCart("good")
        good.add_item("a", 100.0, 1)
        result = batch_checkout_users(
            {"bad": self._BadCart("bad"), "good": good}, 0.0
        )
        assert result["bad"] == 0.0
        assert result["good"] == 100.0

    def test_invalid_ratio_rejected(self):
        cart = ShoppingCart("u")
        cart.add_item("a", 10.0, 1)
        with pytest.raises(InvalidDiscountError):
            batch_checkout_users({"u": cart}, 1.5)
        with pytest.raises(InvalidDiscountError):
            batch_checkout_users({"u": cart}, "0.5")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 设计模式收益：开闭原则 + 依赖倒置 + 上下文管理器
# --------------------------------------------------------------------------- #
class TestPatterns:
    def test_new_coupon_without_modifying_cart(self):
        """开闭原则：新增券种只需注册新策略类，apply_coupon 零改动。"""

        class BuyTwoGetOneCoupon(Coupon):
            code = "BUY2GET1"

            def discount(self, total: Decimal, item_count: int) -> Decimal:
                return total * Decimal("0.25")

        cart = ShoppingCart("ocp-user")
        cart.registry.register(BuyTwoGetOneCoupon())
        cart.add_item("a", 100.0, 2)  # total = 200
        assert cart.apply_coupon("BUY2GET1") == 150.0

    def test_registry_injectable(self):
        """依赖倒置：可注入自定义注册表，隔离默认券集合。"""
        registry = CouponRegistry().register(PercentageCoupon("HALF", "0.5"))
        cart = ShoppingCart("di-user", registry=registry)
        cart.add_item("a", 100.0, 1)
        assert cart.apply_coupon("HALF") == 50.0
        assert cart.apply_coupon("VIP90") == 100.0  # 默认券未在注入表中 -> 无折扣

    def test_context_manager_closes_handle(self, tmp_path):
        """上下文管理器：退出 with 后文件句柄应已关闭。"""
        log_file = tmp_path / "access.log"
        with coupon_access_log(str(log_file)) as handle:
            handle.write("hello")
            assert handle.closed is False
        assert handle.closed is True
        assert log_file.read_text() == "hello"

    def test_coupon_logging_writes_file(self, tmp_path):
        log_file = tmp_path / "coupon.log"
        cart = ShoppingCart("u", access_logger=None)
        cart.add_item("a", 100.0, 1)
        cart.apply_coupon("VIP90", log_path=str(log_file))
        assert log_file.exists()
        assert "VIP90" in log_file.read_text()


# --------------------------------------------------------------------------- #
# 向后兼容
# --------------------------------------------------------------------------- #
class TestBackwardCompatibility:
    def test_cart_item_dict_access(self):
        item = CartItem("apple", Decimal("9.90"), 2)
        assert item["name"] == "apple"
        assert item["price"] == Decimal("9.90")
        assert item["qty"] == 2

    def test_legacy_item_tuple_semantics(self):
        """旧代码可能遍历 cart.items 并按下标取值。"""
        cart = ShoppingCart("u")
        cart.add_item("apple", 9.9, 2)
        names = [it["name"] for it in cart.items]
        assert names == ["apple"]

    def test_return_types_are_float(self):
        cart = ShoppingCart("u")
        cart.add_item("a", 100.0, 1)
        assert isinstance(cart.get_total_price(), float)
        assert isinstance(cart.apply_coupon("VIP90"), float)

    def test_legacy_constructor_signature(self):
        cart = ShoppingCart("legacy-user")  # 仅传 user_id，行为与旧版一致
        assert cart.user_id == "legacy-user"
        assert cart.items == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
