from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ShopifyOrder(BaseModel):
    order_id: str
    order_date: date
    customer_email: str = ""
    revenue_brl: Decimal
    is_first_purchase: bool
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
