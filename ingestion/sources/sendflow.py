"""Cliente Sendflow — busca releases, analytics e ações de disparo da comunidade."""

import logging
import os
import time
from datetime import date

import httpx

from ingestion.models.sendflow_models import (
    SendflowAction,
    SendflowAnalytics,
    SendflowGroup,
    SendflowRelease,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://sendflow.pro/sendapi"
_ACTIONS_THROTTLE_S = 11  # API exige ≥10s entre chamadas de listagem de ações
_MAX_PAGES = 10            # teto da API: 1000 ações por paginação (10 × 100)
_RETRY_DELAYS_S = [3, 7, 15]  # aguarda antes de cada retentativa (403/429/5xx)

RATE_LIMIT_CODES = {429, 403}


def _api_keys() -> list[str]:
    """Retorna lista de API keys disponíveis (primária + fallback)."""
    keys = [os.environ["SENDFLOW_API_KEY"]]
    key2 = os.environ.get("SENDFLOW_API_KEY_2", "").strip()
    if key2:
        keys.append(key2)
    return keys


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _get_with_key_fallback(url: str, params: dict | None = None) -> httpx.Response:
    """
    GET com fallback automático entre as duas API keys em caso de rate limit (429/403).
    Cada key tem seu próprio ciclo de retry antes de passar para a próxima.
    Se todas as keys esgotarem as tentativas, lança a última exceção.
    """
    keys = _api_keys()
    last_exc: Exception | None = None

    for key_idx, api_key in enumerate(keys):
        transient = {403, 429, 500, 502, 503, 504}
        with httpx.Client(headers=_headers(api_key), timeout=30) as client:
            for attempt, delay in enumerate(_RETRY_DELAYS_S + [None]):
                resp = client.get(url, params=params or {})

                if resp.status_code not in transient or delay is None:
                    if resp.status_code in RATE_LIMIT_CODES and key_idx + 1 < len(keys):
                        # Rate limit esgotado nesta key — tenta a próxima
                        logger.warning({
                            "event": "sendflow_key_fallback",
                            "url": url,
                            "status": resp.status_code,
                            "key_index": key_idx,
                            "next_key_index": key_idx + 1,
                        })
                        last_exc = httpx.HTTPStatusError(
                            f"Rate limit na key {key_idx}", request=resp.request, response=resp
                        )
                        break  # vai para a próxima key
                    resp.raise_for_status()
                    return resp

                logger.warning({
                    "event": "sendflow_retry",
                    "url": url,
                    "status": resp.status_code,
                    "key_index": key_idx,
                    "attempt": attempt + 1,
                    "wait_s": delay,
                })
                time.sleep(delay)
            else:
                # Esgotou tentativas desta key sem break — segue para próxima se houver
                if key_idx + 1 < len(keys):
                    logger.warning({
                        "event": "sendflow_key_exhausted",
                        "key_index": key_idx,
                        "url": url,
                    })
                    continue

    if last_exc:
        raise last_exc
    raise RuntimeError(f"Todas as {len(keys)} API key(s) do Sendflow esgotaram as tentativas para {url}")


def fetch_releases() -> list[SendflowRelease]:
    """Retorna todas as releases (campanhas de comunidade) da conta."""
    resp = _get_with_key_fallback(f"{_BASE_URL}/releases")
    return [SendflowRelease.model_validate(r) for r in resp.json()]


def fetch_release_groups(release_id: str) -> list[SendflowGroup]:
    """Retorna grupos vinculados a uma release com contagem atual de membros."""
    resp = _get_with_key_fallback(f"{_BASE_URL}/releases/{release_id}/groups")
    return [SendflowGroup.model_validate(g) for g in resp.json()]


def fetch_release_analytics(release_id: str) -> SendflowAnalytics:
    """Retorna analytics históricos (add/remove/clicks por data) de uma release."""
    resp = _get_with_key_fallback(f"{_BASE_URL}/releases/{release_id}/analytics")
    return SendflowAnalytics.model_validate(resp.json())


def fetch_release_actions(
    release_id: str,
    since: date | None = None,
    until: date | None = None,
) -> list[SendflowAction]:
    """
    Retorna ações de disparo (sendMessages, processed=true) de uma release.

    A API /actions não aceita type/processed/limit como query params — esses campos
    existem apenas no body de resposta. Filtragem é feita client-side.
    Pagina respeitando o rate limit de 10s entre chamadas.
    """
    actions: list[SendflowAction] = []
    cursor: str | None = None

    for page in range(_MAX_PAGES):
        if page > 0:
            time.sleep(_ACTIONS_THROTTLE_S)

        params: dict = {"releaseId": release_id}
        if cursor:
            params["cursor"] = cursor

        resp = _get_with_key_fallback(f"{_BASE_URL}/actions", params=params)
        data = resp.json()

        for item in data.get("actions", []):
            action = SendflowAction.model_validate(item)

            logger.debug({
                "event": "sendflow_action_raw",
                "release_id": release_id,
                "action_id": action.id,
                "type": action.type,
                "processed": action.processed,
                "success": action.success,
                "action_date": action.created_at.date().isoformat(),
            })

            if action.type != "sendMessages" or not action.processed:
                continue

            action_date = action.created_at.date()
            if since and action_date < since:
                continue
            if until and action_date > until:
                continue
            actions.append(action)

        cursor = data.get("nextCursor")
        if not cursor:
            break

    logger.info({
        "event": "sendflow_actions_fetched",
        "release_id": release_id,
        "count": len(actions),
    })
    return actions
