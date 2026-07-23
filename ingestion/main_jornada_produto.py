"""Orquestra a carga (manual, sob demanda) da análise Jornada de Produto nas 4 tabelas
fact_jornada_* — não é um cron: roda sempre que o Daniel atualizar a base local em
mc-growth/saida_local/ e mandar subir os dados pra aba Recompra do gerenciadordecrm."""

import logging

from ingestion.analytics.jornada_produto_ingest import (
    montar_fact_afinidade,
    montar_fact_arvore,
    montar_fact_metricas,
    montar_fact_tempo,
)
from ingestion.db.client import get_supabase_client
from ingestion.db.writers import (
    replace_jornada_afinidade,
    replace_jornada_arvore,
    replace_jornada_metricas,
    replace_jornada_tempo,
)

logger = logging.getLogger(__name__)


def run_jornada_produto() -> dict:
    sb = get_supabase_client()

    metricas_written = replace_jornada_metricas(sb, montar_fact_metricas())
    afinidade_written = replace_jornada_afinidade(sb, montar_fact_afinidade())
    tempo_written = replace_jornada_tempo(sb, montar_fact_tempo())
    arvore_written = replace_jornada_arvore(sb, montar_fact_arvore())

    resultado = {
        "metricas_written": metricas_written,
        "afinidade_written": afinidade_written,
        "tempo_written": tempo_written,
        "arvore_written": arvore_written,
    }
    logger.info({"event": "jornada_produto_done", **resultado})
    return resultado


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dotenv import load_dotenv
    load_dotenv()
    result = run_jornada_produto()
    print(result)
