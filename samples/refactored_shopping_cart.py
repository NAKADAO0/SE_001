"""
重构版本：电商购物车与结算模块 (ShoppingCart & Checkout)

针对 demo_shopping_cart.py 的缺陷与风险隐患，本版本引入以下设计模式与原则：

设计模式
--------
1. 策略模式 (Strategy Pattern)
   折扣规则抽象为 ``Coupon`` 策略接口，每个券种是一个独立策略类。
   新增券种只需新增一个策略类并注册，无需改动 ``apply_coupon`` (开闭原则)。
2. 注册表 (Registry) / 依赖注入
   ``CouponRegistry`` 负责策略的登记与查找，购物车通过注入获得策略集合，
   实现"折扣规则"与"结算流程"解耦。
3. 数据传输对象 / 值对象 (DTO / Value Object)
   ``CartItem`` 数据类封装商品三元组，在 ``__post_init__`` 中集中校验，
   消除散落在各处的参数校验逻辑。
4. 上下文管理器 (Context Manager)
   ``coupon_access_log`` 用 ``with`` 保证文件句柄必然释放，杜绝资源泄漏。

SOLID
-----
* SRP: 结算(购物车)、折扣策略、日志记录由三个独立类承担。
* OCP: 新券种 = 新策略类 + 注册一行，主流程零修改。
* DIP: ``ShoppingCart`` 依赖 ``CouponRegistry`` 抽象而非硬编码分支。

向后兼容
--------
``ShoppingCart`` / ``add_item`` / ``get_total_price`` / ``apply_coupon`` /
``get_most_expensive_item`` / ``batch_checkout_users`` 的调用方式保持不变。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, Iterator, List, Mapping, Optional, TextIO

logger = logging.getLogger(__name__)

# 金额统一保留两位小数，采用四舍五入（ROUND_HALF_UP）以匹配业务直觉
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _quantize(value: Decimal) -> Decimal:
    """将 Decimal 规整为两位小数金额。"""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_money(value: float | int | str | Decimal) -> Decimal:
    """将任意数值安全转换为两位小数的 Decimal，规避二进制浮点误差。"""
    try:
        return _quantize(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidItemError(f"非法金额: {value!r}") from exc


# --------------------------------------------------------------------------- #
# 异常层级：可预期的业务异常显式建模，便于调用方精准捕获
# --------------------------------------------------------------------------- #
class CartError(ValueError):
    """购物车业务异常基类。"""


class InvalidItemError(CartError):
    """商品参数非法（负价、非正数量、空名称等）。"""


class EmptyCartError(CartError):
    """购物车为空时执行了需要商品的非法操作。"""


# --------------------------------------------------------------------------- #
# 数据传输对象：商品值对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CartItem:
    """商品值对象。

    在构造阶段完成全部合法性校验，保证进入购物车的元素始终有效。
    """

    name: str
    unit_price: Decimal
    qty: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidItemError("商品名称必须为非空字符串")
        object.__setattr__(self, "name", self.name.strip())

        money = to_money(self.unit_price)
        if money < ZERO:
            raise InvalidItemError(f"商品价格不能为负，当前: {self.unit_price!r}")
        object.__setattr__(self, "unit_price", money)

        if isinstance(self.qty, bool) or not isinstance(self.qty, int) or self.qty <= 0:
            raise InvalidItemError(f"商品数量必须为正整数，当前: {self.qty!r}")

    @property
    def subtotal(self) -> Decimal:
        """该行小计金额。"""
        return _quantize(self.unit_price * self.qty)

    def __getitem__(self, key: str) -> object:
        """向后兼容旧版字典访问方式 ``item["name"] / item["price"] / item["qty"]``。"""
        legacy = {"name": self.name, "price": self.unit_price, "qty": self.qty}
        try:
            return legacy[key]
        except KeyError as exc:
            raise KeyError(f"CartItem 无此字段: {key}") from exc


# --------------------------------------------------------------------------- #
# 策略模式：折扣规则
# --------------------------------------------------------------------------- #
class Coupon(ABC):
    """优惠券策略抽象基类。每种券实现自身折扣算法。"""

    code: str

    @abstractmethod
    def discount(self, total: Decimal, item_count: int) -> Decimal:
        """计算原始折扣金额（可能超过总额，由调用方归一化）。

        Args:
            total: 购物车总价。
            item_count: 购物车商品行数。

        Returns:
            原始折扣金额。
        """
        raise NotImplementedError


class PercentageCoupon(Coupon):
    """按比例折扣，如 VIP90 九折 -> 折扣 = 总价 * rate。"""

    def __init__(self, code: str, rate: float | str | Decimal) -> None:
        self.code = code
        self.rate = Decimal(str(rate))

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        return total * self.rate


class FixedAmountCoupon(Coupon):
    """固定金额立减，不高于总额（避免负支付）。"""

    def __init__(self, code: str, amount: float | str | Decimal) -> None:
        self.code = code
        self.amount = to_money(amount)

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        return min(self.amount, total)


class ShareDiscountCoupon(Coupon):
    """按商品行均价分享折扣；空购物车时显式抛业务异常。"""

    def __init__(self, code: str, share: float | str | Decimal = "0.5") -> None:
        self.code = code
        self.share = Decimal(str(share))

    def discount(self, total: Decimal, item_count: int) -> Decimal:
        if item_count <= 0:
            raise EmptyCartError(f"{self.code} 需要购物车中存在商品")
        return (total / item_count) * self.share


class CouponRegistry:
    """优惠券策略注册表：负责登记与查找，实现开闭原则。"""

    def __init__(self) -> None:
        self._coupons: Dict[str, Coupon] = {}

    def register(self, coupon: Coupon) -> "CouponRegistry":
        """注册一个券策略，返回自身以支持链式调用。"""
        self._coupons[coupon.code] = coupon
        return self

    def get(self, code: str) -> Optional[Coupon]:
        """按券码查找策略；不存在返回 None（对应"无折扣"）。"""
        return self._coupons.get(code)


def build_default_registry() -> CouponRegistry:
    """构建默认券集合。新增券种在此登记一行即可。"""
    return (
        CouponRegistry()
        .register(PercentageCoupon("VIP90", "0.1"))
        .register(FixedAmountCoupon("MINUS50", "50.00"))
        .register(ShareDiscountCoupon("SHARE_DISCOUNT"))
    )


# --------------------------------------------------------------------------- #
# 上下文管理器：资源安全打开 / 释放
# --------------------------------------------------------------------------- #
@contextmanager
def coupon_access_log(path: str) -> Iterator[TextIO]:
    """以追加模式打开日志文件，退出时必然关闭句柄（杜绝资源泄漏）。"""
    handle = open(path, "a", encoding="utf-8")
    try:
        yield handle
    finally:
        handle.close()


class CouponAccessLogger:
    """优惠券访问日志记录器：单一职责，与结算逻辑解耦。"""

    def __init__(self, path: str = "coupon_access_log.txt") -> None:
        self.path = path

    def record(self, user_id: str, coupon_code: str, discount: Decimal) -> None:
        """安全写入访问日志；IO 失败仅告警，不影响结算主流程。"""
        try:
            with coupon_access_log(self.path) as handle:
                handle.write(
                    f"User {user_id} applied {coupon_code} "
                    f"discount={discount} at {time.time()}\n"
                )
        except OSError as exc:  # 日志故障不应让结算崩溃
            logger.warning("写入优惠券日志失败: %s", exc)


def _clamp_discount(discount: Decimal, total: Decimal) -> Decimal:
    """将折扣归一到 [0, total]，防止负折扣或折扣高于总额造成负支付金额。"""
    if discount < ZERO:
        return ZERO
    return total if discount > total else _quantize(discount)


# --------------------------------------------------------------------------- #
# 购物车
# --------------------------------------------------------------------------- #
class ShoppingCart:
    """购物车：负责商品聚合与总价计算，折扣委托给策略对象。"""

    def __init__(
        self,
        user_id: str,
        registry: Optional[CouponRegistry] = None,
        access_logger: Optional[CouponAccessLogger] = None,
    ) -> None:
        if not user_id:
            raise ValueError("user_id 不能为空")
        self.user_id: str = user_id
        self.items: List[CartItem] = []
        # 依赖注入：默认使用内置券集合，也可外部传入以扩展/替换
        self.registry: CouponRegistry = registry or build_default_registry()
        self.access_logger: CouponAccessLogger = access_logger or CouponAccessLogger()

    def add_item(self, name: str, price: float, qty: int = 1) -> None:
        """添加商品；非法参数由 ``CartItem`` 构造时拦截。"""
        self.items.append(CartItem(name=name, unit_price=to_money(price), qty=qty))

    def get_total_price(self) -> Decimal:
        """计算总价：Decimal 累加，规避浮点误差。"""
        return _quantize(sum((item.subtotal for item in self.items), ZERO))

    def apply_coupon(
        self, coupon_code: str, log_path: Optional[str] = None
    ) -> Decimal:
        """应用优惠券并返回折后价格。

        Args:
            coupon_code: 券码，未知券码按无折扣处理。
            log_path: 兼容旧接口的日志路径覆盖项。

        Returns:
            折后价格（两位小数 Decimal）。

        Raises:
            EmptyCartError: 券种要求购物车非空但购物车为空时。
        """
        total = self.get_total_price()
        coupon = self.registry.get(coupon_code)
        raw_discount = coupon.discount(total, len(self.items)) if coupon else ZERO
        discount = _clamp_discount(raw_discount, total)

        access_logger = (
            CouponAccessLogger(log_path) if log_path is not None else self.access_logger
        )
        access_logger.record(self.user_id, coupon_code, discount)

        return _quantize(total - discount)

    def get_most_expensive_item(self) -> Optional[CartItem]:
        """返回单价最高的商品；购物车为空时返回 None（不再抛 ValueError）。"""
        if not self.items:
            return None
        return max(self.items, key=lambda item: item.unit_price)


# --------------------------------------------------------------------------- #
# 批量结算
# --------------------------------------------------------------------------- #
def batch_checkout_users(
    user_carts: Mapping[str, ShoppingCart], discount_ratio: float
) -> Dict[str, Decimal]:
    """批量结算。

    Args:
        user_carts: {用户ID: 购物车} 映射。
        discount_ratio: 统一折扣比例，必须位于 [0, 1]。

    Returns:
        {用户ID: 结算金额}。

    Raises:
        ValueError: discount_ratio 越界或类型非法。
    """
    if isinstance(discount_ratio, bool) or not isinstance(
        discount_ratio, (int, float, Decimal)
    ):
        raise ValueError(f"discount_ratio 必须为数值，当前: {discount_ratio!r}")

    ratio = Decimal(str(discount_ratio))
    if not (ZERO <= ratio <= Decimal("1")):
        raise ValueError(f"discount_ratio 必须在 [0, 1] 之间，当前: {discount_ratio!r}")

    price_factor = Decimal("1") - ratio
    results: Dict[str, Decimal] = {}
    for uid, cart in user_carts.items():
        try:
            total = cart.get_total_price()
        except CartError as exc:
            # 仅捕获可预期的业务异常
            logger.error("结算用户 %s 失败(业务异常): %s", uid, exc)
            results[uid] = ZERO
        except (TypeError, AttributeError, ArithmeticError) as exc:
            # 捕获预期外异常但记录堆栈，避免静默吞没；不再吞掉 KeyboardInterrupt
            logger.exception("结算用户 %s 发生意外错误: %s", uid, exc)
            results[uid] = ZERO
        else:
            results[uid] = _quantize(total * price_factor)
    return results
