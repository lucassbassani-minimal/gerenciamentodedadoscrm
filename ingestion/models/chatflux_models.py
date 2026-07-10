"""Modelos Pydantic para eventos de disparo/resposta do Chatflux (WhatsApp)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatfluxEvento(BaseModel):
    model_config = {"populate_by_name": True}

    event_timestamp: datetime = Field(alias="timestamp")
    segmento: Literal["Welcome Novos", "Welcome Recorrentes", "Carrinho Abandonado"]
    etapa: Literal["disparo", "resposta"]
    telefone: str

    @field_validator("telefone", mode="before")
    @classmethod
    def strip_telefone(cls, v: object) -> str:
        val = str(v).strip() if v is not None else ""
        if not val:
            raise ValueError(f"Telefone vazio: recebido '{v}'")
        return val
