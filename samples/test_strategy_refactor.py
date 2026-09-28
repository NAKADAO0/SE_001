"""针对策略模式重构的增强测试：验证开闭原则与裸 except 修复。"""

from decimal import Decimal

import pytest

from refactored_shopping_cart import (
    CartError,
    Coupon,
    EmptyCartError,
    ShoppingCart,
    batch_checkout_users,
)


class TestOpenClosedExtensibility:
    """新增券种无需修改 apply_coupon —— 只需注册新策略类。"""

    def test_register_custom_coupon_without_touching_cart(self):
        class BuyTwoGetOneCoupon(Coupon):
            code = "BUY2GET1"

            def discount(self, total: Decimal, item_count: int) -> Decimal:
                # 自定义策略：满两行免最低价一行（示例）
                return total * Decimal("0.25")

        cart = ShoppingCart("ocp-user")
        cart.registry.register(BuyTwoGetOneCoupon())
        cart.add_item("a", 100.0, 2)  # total=200
        assert cart.apply_coupon("BUY2GET1") == Decimal("150.00")

    def test_registry_is_injectable(self):
        """依赖注入：可传入自定义注册表隔离默认券集合。"""
        from refactored_shopping_cart import CouponRegistry, PercentageCoupon

        registry = CouponRegistry().register(PercentageCoupon("HALF", "0.5"))
        cart = ShoppingCart("di-user", registry=registry)
        cart.add_item("a", 100.0, 1)
        assert cart.apply_coupon("HALF") == Decimal("50.00")
        # 默认券不在注入的注册表中 -> 视为无折扣
        assert cart.apply_coupon("VIP90") == Decimal("100.00")


class TestBareExceptFixed:
    """裸 except 修复：致命异常（KeyboardInterrupt / SystemExit）必须向上传播。"""

    class _ExplodingCart(ShoppingCart):
        def get_total_price(self) -> Decimal:
            raise KeyboardInterrupt

    def test_keyboard_interrupt_not_swallowed(self):
        with pytest.raises(KeyboardInterrupt):
            batch_checkout_users({"u1": self._ExplodingCart("u1")}, 0.1)

    def test_business_error_is_isolated_per_user(self):
        class _BadCart(ShoppingCart):
            def get_total_price(self) -> Decimal:
                raise CartError("boom")

        good = ShoppingCart("good")
        good.add_item("a", 100.0, 1)
        result = batch_checkout_users({"bad": _BadCart("bad"), "good": good}, 0.0)
        assert result["bad"] == Decimal("0.00")
        assert result["good"] == Decimal("100.00")

    def test_invalid_ratio_type_rejected(self):
        cart = ShoppingCart("u")
        cart.add_item("a", 10.0, 1)
        with pytest.raises(ValueError):
            batch_checkout_users({"u": cart}, "0.5")  # type: ignore[arg-type]


class TestFixedBugsRegression:
    def test_share_discount_empty_cart_raises_business_error(self):
        with pytest.raises(EmptyCartError):
            ShoppingCart("e").apply_coupon("SHARE_DISCOUNT")

    def test_empty_cart_most_expensive_is_none(self):
        assert ShoppingCart("e").get_most_expensive_item() is None

    def test_negative_price_rejected(self):
        from refactored_shopping_cart import InvalidItemError

        with pytest.raises(InvalidItemError):
            ShoppingCart("e").add_item("x", -1.0, 1)
