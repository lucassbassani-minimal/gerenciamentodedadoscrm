from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class OrderHistoryLineItem(BaseModel):
    order_name: str
    shopify_order_id: str | None = None
    line_number: int
    email: str | None = None
    financial_status: Literal["paid"]
    paid_at: datetime | None = None
    created_at_shopify: datetime
    order_total_brl: Decimal
    order_subtotal_brl: Decimal | None = None
    discount_code: str | None = None
    discount_amount_brl: Decimal | None = None
    shipping_method: str | None = None
    billing_province: str | None = None
    lineitem_quantity: int
    lineitem_name: str
    lineitem_price: Decimal
    lineitem_sku: str | None = None
