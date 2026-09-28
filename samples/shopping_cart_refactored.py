"""
电商购物车与结算模块 —— 架构重构版 (Refactored)
================================================

针对原始 ``demo_shopping_cart.py`` 的坏味道与缺陷，本版本做了如下重构：

设计模式
--------
1. 策略模式 (Strategy Pattern)
   把 ``apply_coupon`` 中硬编码的 ``if/elif`` 券种分支，抽象为 ``Coupon`` 策略接口，
   每个券种 = 一个独立策略类（``PercentageCoupon`` / ``FixedAmountCoupon`` /
   ``ShareDiscountCoupon``）。新增券种只需新增策略类，主流程零改动 —— 满足开闭原则。

2. 注册表 + 依赖注入 (Registry / DI)
   ``CouponRegistry`` 负责策略的登记与查找；``ShoppingCart`` 通过构造参数注入
   registry / logger，使"结算流程"依赖抽象而非具体实现 —— 满足依赖倒置。

3. 数据类 / 传输对象 (dataclass / DTO)
   ``CartItem`` 封装商品三元组，在 ``__post_init__`` 中集中校验，消除散落各处的
   参数防御代码，同时避免"裸字典"带来的键名拼写风险。

4. 上下文管理器 (Context Manager)
   日志写入统一走 ``coupon_access_log`` (基于 ``with``)，保证文件句柄必然释放，
   杜绝资源泄漏。

SOLID 与健壮性
--------------
* SRP：结算(购物车) / 折扣策略 / 日志持久化 拆分为三个独立职责。
* 金额计算改用 ``Decimal``，`0.1 + 0.2` 类浮点误差归零。
* 折扣统一裁剪到 ``[0, total]``，杜绝"优惠大于总额"的负支付。
* 自定义异常层级替代裸 ``except``；批量结算只捕获可预期异常，
  不再吞没 ``KeyboardInterrupt`` / ``SystemExit``。

向后兼容
--------
* ``ShoppingCart(user_id, ...)``、``add_item``、``get_total_price``、
  ``apply_coupon``、``get_most_expensive_item``、``batch_checkout_users`` 的
  **调用方式与返回类型** 保持不变（均返回 ``float`` / 旧字典语义）。
* ``get_most_expensive_item`` 空车时抛出 ``EmptyCartError``，
  它继承 ``ValueError``，旧调用方原有的 ``except ValueError`` 仍然生效。
* ``CartItem`` 支持 ``item["name"] / item["price"] / item["qty"]`` 下标访问，
  兼容旧代码对字典元素的读取习惯。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, Iterator, List, Mapping, Optional, TextIO

logger = logging.getLogger(__name__)

#: 金额精度：统一保留两位小数，四舍五入以贴合业务直觉
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1")


# --------------------------------------------------------------------------- #
# 金额工具
# --------------------------------------------------------------------------- #
def to_money(value: object) -> Decimal:
    """把任意数值安全转换为两位小数的 ``Decimal``，规避二进制浮点误差。

    Raises:
        InvalidItemError: 当入参无法解析为合法金额时。
    """
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidItemError(f"非法金额: {value!r}") from exc


def _clamp_discount(discount: Decimal, total: Decimal) -> Decimal:
    """将折扣裁剪到 ``[0, total]``，防止负折扣或超额折扣导致负支付金额。"""
    if discount < ZERO:
        return ZERO
    return total if discount > total else discount


# --------------------------------------------------------------------------- #
# 异常层级：把"可预期的业务异常"显式建模，便于调用方精准捕获
# --------------------------------------------------------------------------- #
class CartError(ValueError):
    """购物车业务异常基类（继承 ValueError，兼容旧版捕获习惯）。"""


class InvalidItemError(CartError):
    """商品参数非法（负价、非正数量、空名称、非法金额等）。"""


class EmptyCartError(CartError):
    """在空购物车上执行了需要商品的操作。"""


class InvalidDiscountError(CartError):
    """批量结算的折扣比例非法（越界或非数值）。"""


# --------------------------------------------------------------------------- #
# 数据类 / DTO：商品值对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CartItem:
    """商品值对象。

    在构造阶段完成全部合法性校验，保证进入购物车的元素始终有效。
    支持旧版字典下标访问 ``item["name"] / item["price"] / item["qty"]``。
    """

    name: str
    unit_price: Decimal
    qty: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidItemError(f"商品名称必须为非空字符串，当前: {self.name!r}")
        object.__setattr__(self, "name", self.name.strip())

        money = to_money(self.unit_price)
        if money < ZERO:
            raise InvalidItemError(f"商品单价不能为负，当前: {self.unit_price!r}")
        object.__setattr__(self, "unit_price", money)

        if isinstance(self.qty, bool) or not isinstance(self.qty, int) or self.qty <= 0:
            raise InvalidItemError(f"商品数量必须为正整数，当前: {self.qty!r}")

    @property
    def subtotal(self) -> Decimal:
        """该商品行小计金额 = 单价 × 数量（两位小数）。"""
        return (self.unit_price * self.qty).quantize(CENT, rounding=ROUND_HALF_UP)

    def __getitem__(self, key: str) -> object:
        """兼容旧版 ``dict`` 下标访问：``item["price"]`` 等价于 ``item.unit_price``。"""
        legacy = {"name": self.name, "price": self.unit_price, "qty": self.qty}
        try:
            return legacy[key]
        except KeyError as exc:
            raise KeyError(f"CartItem 不存在字段: {key!r}") from exc


# --------------------------------------------------------------------------- #
# 策略模式：折扣规则
# --------------------------------------------------------------------------- #
class Coupon(ABC):
    """优惠券策略抽象基类。每种券实现自身的折扣算法。"""

    code: str

    @abstractmethod
    def discount(self, total: Decimal, item_count: int) -> Decimal:
        """计算原始折扣金额（可能超过总额，由调用方统一裁剪）。

        Args:
            total: 购物车总价。
            item_count: 购物车商品行数。

        Returns:
            原始折扣金额（未裁剪）。
        """
        raise NotImplementedError


class PercentageCoupon(Coupon):
    """按比例折扣。例：VIP90 九折 -> 折扣 = 总价 × 0.1。"""

    def __init__(self, code: str, rate: float | str | Decimal) -> None:
        rate_d = Decimal(str(rate))
        if not (ZERO <= rate_d <= ONE):
            raise ValueError(f"折扣比例必须位于 [0, 1]，当前: {rate!r}")
        self.code = code
        self.rate = rate_d

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        return total * self.rate


class FixedAmountCoupon(Coupon):
    """固定金额立减，金额不高于总额（避免负支付）。"""

    def __init__(self, code: str, amount: float | str | Decimal) -> None:
        self.code = code
        self.amount = to_money(amount)

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        return min(self.amount, total)


class ShareDiscountCoupon(Coupon):
    """按商品行均价的指定比例分享折扣；空购物车时显式抛业务异常。"""

    def __init__(self, code: str, share: float | str | Decimal = "0.5") -> None:
        self.code = code
        self.share = Decimal(str(share))

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        if item_count <= 0:
            # 修复原 ZeroDivisionError：转换为可预期的业务异常
            raise EmptyCartError(f"优惠券 {self.code} 要求购物车非空")
        return (total / item_count) * self.share


class CouponRegistry:
    """优惠券策略注册表：负责策略登记与查找，实现开闭原则。"""

    def __init__(self) -> None:
        self._coupons: Dict[str, Coupon] = {}

    def register(self, coupon: Coupon) -> "CouponRegistry":
        """登记一个券策略，返回自身以支持链式调用。"""
        self._coupons[coupon.code] = coupon
        return self

    def get(self, code: str) -> Optional[Coupon]:
        """按券码查找策略；不存在返回 ``None``（对应"无折扣"）。"""
        return self._coupons.get(code)


def build_default_registry() -> CouponRegistry:
    """构建默认券集合。新增券种在此登记一行即可，主流程无需改动。"""
    return (
        CouponRegistry()
        .register(PercentageCoupon("VIP90", "0.1"))
        .register(FixedAmountCoupon("MINUS50", "50.00"))
        .register(ShareDiscountCoupon("SHARE_DISCOUNT"))
    )


# --------------------------------------------------------------------------- #
# 上下文管理器 + SRP：资源安全打开 / 日志持久化
# --------------------------------------------------------------------------- #
@contextmanager
def coupon_access_log(path: str) -> Iterator[TextIO]:
    """以追加模式打开优惠券访问日志，退出时必然关闭句柄（杜绝资源泄漏）。"""
    handle = open(path, "a", encoding="utf-8")
    try:
        yield handle
    finally:
        handle.close()


class CouponAccessLogger:
    """优惠券访问日志记录器：单一职责，与结算逻辑彻底解耦。"""

    def __init__(self, path: str = "coupon_access_log.txt") -> None:
        self.path = path

    def record(self, user_id: object, coupon_code: str, discount: Decimal) -> None:
        """安全写入访问日志；IO 失败仅告警，不影响结算主流程。"""
        try:
            with coupon_access_log(self.path) as handle:
                handle.write(
                    f"User {user_id} applied {coupon_code} "
                    f"discount={discount} at {time.time()}\n"
                )
        except OSError as exc:
            logger.warning("写入优惠券访问日志失败: %s", exc)


# --------------------------------------------------------------------------- #
# 购物车：商品聚合 + 结算编排
# --------------------------------------------------------------------------- #
class ShoppingCart:
    """购物车：负责商品聚合与总价计算，折扣计算委托给策略对象。"""

    def __init__(
        self,
        user_id: object,
        registry: Optional[CouponRegistry] = None,
        access_logger: Optional[CouponAccessLogger] = None,
    ) -> None:
        self.user_id = user_id
        self.items: List[CartItem] = []
        # 依赖注入：默认内置券集合，亦可外部传入以扩展 / 替换
        self.registry: CouponRegistry = registry or build_default_registry()
        self.access_logger: CouponAccessLogger = access_logger or CouponAccessLogger()

    def add_item(self, name: str, price: float, qty: int = 1) -> None:
        """添加商品。非法参数（负价 / 非正数量 / 空名称）由 ``CartItem`` 拦截。"""
        self.items.append(CartItem(name=name, unit_price=to_money(price), qty=qty))

    def get_total_price(self) -> float:
        """计算总价。内部用 ``Decimal`` 累加以规避浮点误差，对外返回 ``float``（保持兼容）。"""
        total = sum((item.subtotal for item in self.items), ZERO)
        return float(total)

    def apply_coupon(self, coupon_code: str, log_path: Optional[str] = None) -> float:
        """应用优惠券并返回折后价格（``float``，两位小数）。

        Args:
            coupon_code: 券码；未知券码按"无折扣"处理（保持旧行为）。
            log_path: 可选，覆盖访问日志路径（兼容 / 便于测试）。

        Returns:
            折后价格。

        Raises:
            EmptyCartError: 券种要求购物车非空但购物车为空时。
        """
        total = sum((item.subtotal for item in self.items), ZERO)

        coupon = self.registry.get(coupon_code)
        raw_discount = coupon.discount(total, len(self.items)) if coupon else ZERO
        discount = _clamp_discount(raw_discount, total)

        access_logger = (
            CouponAccessLogger(log_path) if log_path is not None else self.access_logger
        )
        access_logger.record(self.user_id, coupon_code, discount)

        final_price = (total - discount).quantize(CENT, rounding=ROUND_HALF_UP)
        return float(final_price)

    def get_most_expensive_item(self) -> CartItem:
        """返回单价最高的商品（``CartItem``，支持旧字典下标访问）。

        Raises:
            EmptyCartError: 购物车为空时（继承 ``ValueError``，兼容旧捕获）。
        """
        if not self.items:
            raise EmptyCartError("购物车为空，无法获取最贵商品")
        return max(self.items, key=lambda item: item.unit_price)


# --------------------------------------------------------------------------- #
# 批量结算
# --------------------------------------------------------------------------- #
def batch_checkout_users(
    user_carts: Mapping[str, ShoppingCart], discount_ratio: float
) -> Dict[str, float]:
    """批量结算多个用户的购物车。

    Args:
        user_carts: ``{用户ID: 购物车}`` 映射。
        discount_ratio: 统一折扣比例，必须位于 ``[0, 1]``。

    Returns:
        ``{用户ID: 结算金额(float)}``；单个用户结算失败时记为 ``0.0``。

    Raises:
        InvalidDiscountError: ``discount_ratio`` 越界或类型非法。
    """
    if isinstance(discount_ratio, bool) or not isinstance(
        discount_ratio, (int, float, Decimal)
    ):
        raise InvalidDiscountError(f"discount_ratio 必须为数值，当前: {discount_ratio!r}")

    ratio = Decimal(str(discount_ratio))
    if not (ZERO <= ratio <= ONE):
        raise InvalidDiscountError(
            f"discount_ratio 必须位于 [0, 1]，当前: {discount_ratio!r}"
        )

    price_factor = ONE - ratio
    results: Dict[str, float] = {}
    for uid, cart in user_carts.items():
        try:
            total = Decimal(str(cart.get_total_price()))
            results[uid] = float((total * price_factor).quantize(CENT, rounding=ROUND_HALF_UP))
        except CartError as exc:
            # 仅捕获可预期的业务异常
            logger.error("结算用户 %s 失败(业务异常): %s", uid, exc)
            results[uid] = 0.0
        except (TypeError, AttributeError, ArithmeticError) as exc:
            # 预期外异常也记录堆栈，绝不静默吞没；KeyboardInterrupt/SystemExit 自然会向上冒泡
            logger.exception("结算用户 %s 发生意外错误: %s", uid, exc)
            results[uid] = 0.0
    return results
