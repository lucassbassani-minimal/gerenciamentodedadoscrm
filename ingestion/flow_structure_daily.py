"""
Sincronização diária da estrutura de fluxos Klaviyo -> dim_assets + dim_asset_items.

Deve rodar antes do cron email_flow (03:00 BRT vs 04:00 BRT) para garantir que
o mapa de mensagens esteja atualizado quando as métricas forem buscadas.

Uso:
  python -m ingestion.flow_structure_daily
"""
import logging
import sys

from dotenv import load_dotenv

from ingestion.db.client import get_supabase_client
from ingestion.sources.klaviyo_structure_sync import sync_flow_structure

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_structure_sync() -> None:
    logger.info({"event": "structure_sync_start"})
    try:
        sb = get_supabase_client()
        flows_n, messages_n = sync_flow_structure(sb)
        logger.info({
            "event": "structure_sync_done",
            "flows_upserted": flows_n,
            "messages_upserted": messages_n,
        })
    except Exception as e:
        logger.error({"event": "structure_sync_failed", "error": str(e)})
        raise


if __name__ == "__main__":
    run_structure_sync()
