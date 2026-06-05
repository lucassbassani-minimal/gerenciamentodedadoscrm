from __future__ import annotations
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class KlaviyoFlow(BaseModel):
    id: str
    name: str
    status: Literal["live", "draft", "manual", "paused"]
    trigger_type: str | None = None
    created: datetime | None = None
    updated: datetime | None = None


class KlaviyoFlowMessage(BaseModel):
    id: str
    flow_id: str
    name: str
    position: int | None = None
    created: datetime | None = None
    updated: datetime | None = None


class KlaviyoCampaign(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    send_time: datetime | None = None


class KlaviyoCampaignMessage(BaseModel):
    id: str
    campaign_id: str
    label: str
    created_at: datetime
    updated_at: datetime


class KlaviyoEmailMetricRow(BaseModel):
    message_id: str
    date: date
    sends: int = 0
    opens: int = 0
    clicks: int = 0
    bounces: int = 0
    spam_complaints: int = 0
    unsubscribes: int = 0


class KlaviyoForm(BaseModel):
    id: str
    name: str
    status: str
    form_type: str = "form"
    created_at: datetime
    updated_at: datetime


class KlaviyoFormMetricRow(BaseModel):
    form_external_id: str
    date: date
    impressions: int = 0
    submissions: int = 0


class KlaviyoCampaignEmailMetric(BaseModel):
    campaign_id: str
    campaign_name: str
    message_id: str
    data: date
    email_enviado: int = 0
    email_aberto: int = 0
    email_clicado: int = 0


class KlaviyoFlowEmailMetric(BaseModel):
    flow_id: str
    flow_name: str
    message_id: str
    message_name: str
    data: date
    email_enviado: int = 0
    email_aberto: int = 0
    email_clicado: int = 0
