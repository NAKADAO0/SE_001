"""针对重构版 ShoppingCart 的回归测试：覆盖原始缺陷场景与向后兼容性。"""

import pytest

from shopping_cart_refactored import (
    CartItem,
    EmptyCartError,
    InvalidDiscountError,
    InvalidItemError,
    PercentageCoupon,
    ShoppingCart,
    batch_checkout_users,
    build_default_registry,
)


# --------------------------------------------------------------------------- #
# 原缺陷回归
# --------------------------------------------------------------------------- #
class TestFixedBugs:
    def test_share_discount_empty_cart_no_zero_division(self):
        """原缺陷1：空车 SHARE_DISCOUNT 不再 ZeroDivisionError，而是业务异常。"""
        cart = ShoppingCart("u1")
        with pytest.raises(EmptyCartError):
            cart.apply_coupon("SHARE_DISCOUNT")

    def test_most_expensive_item_empty_raises_empty_cart_error(self):
        """原缺陷2：空车不再抛裸 ValueError，改为继承 ValueError 的业务异常。"""
        cart = ShoppingCart("u2")
        with pytest.raises(EmptyCartError):
            cart.get_most_expensive_item()
        # 兼容旧调用方：EmptyCartError 仍属于 ValueError
        with pytest.raises(ValueError):
            cart.get_most_expensive_item()

    def test_add_item_rejects_negative_price(self):
        """原缺陷4：负价被拦截。"""
        cart = ShoppingCart("u3")
        with pytest.raises(InvalidItemError):
            cart.add_item("恶意商品", -100.0, 3)

    def test_add_item_rejects_non_positive_qty(self):
        cart = ShoppingCart("u4")
        with pytest.raises(InvalidItemError):
            cart.add_item("正常商品", 10.0, 0)

    def test_discount_never_negative(self):
        """原缺陷：折扣不得超过总额，避免负支付。"""
        cart = ShoppingCart("u5")
        cart.add_item("小商品", 10.0, 1)  # 10 元，MINUS50 至多扣 10
        assert cart.apply_coupon("MINUS50") == 0.0

    def test_batch_rejects_ratio_gt_1(self):
        """原缺陷5：discount_ratio > 1 被拦截，而非产生负金额。"""
        cart = ShoppingCart("u6")
        cart.add_item("a", 100.0, 1)
        with pytest.raises(InvalidDiscountError):
            batch_checkout_users({"u6": cart}, 1.5)

    def test_file_handle_released_after_apply(self, tmp_path):
        """原缺陷3：句柄用 with 自动关闭，文件可安全删除（Windows 未关会失败）。"""
        log = tmp_path / "log.txt"
        cart = ShoppingCart("u7")
        cart.add_item("a", 100.0, 1)
        cart.apply_coupon("VIP90", log_path=str(log))
        assert log.exists()
        log.unlink()
        assert not log.exists()

    def test_bare_except_no_longer_swallows_keyboard_interrupt(self):
        """裸 except 已消除：KeyboardInterrupt 不被吞没，正常向上冒泡。"""

        class ExplodingCart(ShoppingCart):
            def get_total_price(self):
                raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            batch_checkout_users({"k": ExplodingCart("k")}, 0.1)


# --------------------------------------------------------------------------- #
# 业务逻辑与数值精度
# --------------------------------------------------------------------------- #
class TestBusinessLogic:
    def test_vip90_discount(self):
        cart = ShoppingCart("u8")
        cart.add_item("a", 100.0, 2)  # 200 -> 九折扣 20 -> 180
        assert cart.apply_coupon("VIP90") == 180.0

    def test_minus50_capped(self):
        cart = ShoppingCart("u8b")
        cart.add_item("a", 100.0, 1)  # 100 -> 扣 50 -> 50
        assert cart.apply_coupon("MINUS50") == 50.0

    def test_share_discount_counts_distinct_lines(self):
        """按商品行数取平均：2 行各 100 -> avg=100，扣 50 -> 150。"""
        cart = ShoppingCart("u9")
        cart.add_item("a", 100.0, 1)
        cart.add_item("b", 100.0, 1)
        assert cart.apply_coupon("SHARE_DISCOUNT") == 150.0

    def test_unknown_coupon_no_discount(self):
        """未知券码保持旧行为：无折扣。"""
        cart = ShoppingCart("u10")
        cart.add_item("a", 50.0, 1)
        assert cart.apply_coupon("NOT_EXIST") == 50.0

    def test_decimal_accuracy(self):
        """0.1 + 0.2 不应出现浮点误差。"""
        cart = ShoppingCart("u11")
        cart.add_item("a", 0.1, 1)
        cart.add_item("b", 0.2, 1)
        assert cart.get_total_price() == 0.3

    def test_most_expensive_item_name(self):
        cart = ShoppingCart("u12")
        cart.add_item("cheap", 10.0)
        cart.add_item("pricey", 99.0)
        item = cart.get_most_expensive_item()
        assert item.name == "pricey"
        # 兼容旧字典访问语义
        assert item["name"] == "pricey"
        assert item["price"] == pytest.approx(99.0)

    def test_batch_checkout_valid(self):
        carts = {}
        for i in range(3):
            c = ShoppingCart(f"u{i}")
            c.add_item("a", 100.0, 1)
            carts[f"u{i}"] = c
        res = batch_checkout_users(carts, 0.1)
        assert all(v == 90.0 for v in res.values())

    def test_batch_checkout_ratio_zero(self):
        cart = ShoppingCart("u13")
        cart.add_item("a", 100.0, 1)
        assert batch_checkout_users({"u13": cart}, 0.0) == {"u13": 100.0}


# --------------------------------------------------------------------------- #
# 向后兼容
# --------------------------------------------------------------------------- #
class TestBackwardCompatibility:
    def test_get_total_price_returns_float(self):
        cart = ShoppingCart("c1")
        cart.add_item("a", 9.99, 3)
        assert isinstance(cart.get_total_price(), float)

    def test_apply_coupon_returns_float(self):
        cart = ShoppingCart("c2")
        cart.add_item("a", 100.0, 1)
        assert isinstance(cart.apply_coupon("VIP90"), float)

    def test_legacy_positional_call_signature(self):
        """旧调用方式：ShoppingCart(uid) / add_item(name, price, qty) 依旧可用。"""
        cart = ShoppingCart("c3")
        cart.add_item("a", 10.0, 2)
        assert cart.get_total_price() == 20.0


# --------------------------------------------------------------------------- #
# 开闭原则：扩展新券种无需改动既有代码
# --------------------------------------------------------------------------- #
class TestOpenClosed:
    def test_register_new_coupon_without_touching_cart(self):
        class HalfOffCoupon(PercentageCoupon):
            pass

        registry = build_default_registry().register(HalfOffCoupon("HALF", "0.5"))
        cart = ShoppingCart("o1", registry=registry)
        cart.add_item("a", 100.0, 1)
        assert cart.apply_coupon("HALF") == 50.0

    def test_cart_item_direct_validation(self):
        with pytest.raises(InvalidItemError):
            CartItem(name="", unit_price=10.0)
        with pytest.raises(InvalidItemError):
            CartItem(name="x", unit_price=10.0, qty=-1)
