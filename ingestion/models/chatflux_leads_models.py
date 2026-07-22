"""Modelo Pydantic para os totais diários de leads por vendedor do Chatflux (/api/leads)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatfluxLeadDiario(BaseModel):
    day: date
    segmento: Literal["Welcome Novos", "Welcome Recorrentes", "Carrinho Abandonado"]
    vendedor_id: int | None = None
    vendedor_nome: str
    total_leads: int = Field(gt=0)

    @field_validator("vendedor_nome", mode="before")
    @classmethod
    def strip_vendedor_nome(cls, v: object) -> str:
        val = str(v).strip() if v is not None else ""
        if not val:
            raise ValueError(f"Nome de vendedor vazio: recebido '{v}'")
        return val
