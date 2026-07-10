from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OrderHistoryLegacyRow(BaseModel):
    email: str
    order_date: date
    revenue_brl: Decimal
