"""Carrega os resultados da análise Jornada de Produto (mc-growth/jornada_produto.py +
mc-growth/construir_arvore_dashboard.py) a partir dos CSVs/JSON locais e monta os
registros das 4 tabelas fact_jornada_*. Rodado manualmente sempre que o Daniel atualizar
a base local em mc-growth/saida_local/ — não há API automática para essa fonte ainda
(ver cabeçalho de supabase/migrations/20260723000057_jornada_produto.sql)."""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAIDA_LOCAL_DIR = Path(__file__).resolve().parents[2] / "mc-growth" / "saida_local"
COMPRAS_VALIDAS = {"2a", "3a", "4a", "5a"}


def _ler_csv(nome_arquivo: str) -> list[dict[str, str]]:
    caminho = SAIDA_LOCAL_DIR / nome_arquivo
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def _carregar_linhas_requeridas() -> dict[str, list[str]]:
    with open(SAIDA_LOCAL_DIR / "jornada_dados.json", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return {item["nome"]: item["linhas_requeridas"] for item in dados}


def montar_fact_metricas() -> list[dict]:
    ltv_por_entrada = {row["entrada"]: row for row in _ler_csv("ltv_por_entrada.csv")}
    taxas_por_entrada = {row["entrada"]: row for row in _ler_csv("taxas_por_entrada.csv")}
    linhas_requeridas_por_entrada = _carregar_linhas_requeridas()

    registros = []
    for entrada, ltv in ltv_por_entrada.items():
        taxas = taxas_por_entrada[entrada]
        registros.append({
            "entrada": entrada,
            "n_clientes": int(ltv["clientes"]),
            "linhas_requeridas": linhas_requeridas_por_entrada[entrada],
            "ltv_180d_media": float(ltv["ltv_180d_media"]),
            "ltv_180d_mediana": float(ltv["ltv_180d_mediana"]),
            "taxa_repeticao": float(taxas["taxa_repeticao"]),
            "taxa_reativacao": float(taxas["taxa_reativacao"]),
            "pct_recente_hoje": float(taxas["pct_recente_hoje"]),
            "pct_ativo_hoje": float(taxas["pct_ativo_hoje"]),
            "pct_inativo_hoje": float(taxas["pct_inativo_hoje"]),
        })
    return registros


def montar_fact_afinidade() -> list[dict]:
    registros = []
    for row in _ler_csv("afinidade_produtos.csv"):
        if row["compra"] not in COMPRAS_VALIDAS:
            raise ValueError(f"Compra inválida: recebida '{row['compra']}', esperado um de {COMPRAS_VALIDAS}")
        registros.append({
            "entrada": row["entrada"],
            "compra": row["compra"],
            "produto": row["produto"],
            "clientes": int(row["clientes"]),
            "pct_da_entrada": float(row["pct_da_entrada"]),
            "n_base_da_compra": int(row["n_base_da_compra"]),
        })
    return registros


def montar_fact_tempo() -> list[dict]:
    registros = []
    for row in _ler_csv("tempo_entre_compras.csv"):
        if row["compra"] not in COMPRAS_VALIDAS:
            raise ValueError(f"Compra inválida: recebida '{row['compra']}', esperado um de {COMPRAS_VALIDAS}")
        registros.append({
            "entrada": row["entrada"],
            "compra": row["compra"],
            "clientes": int(row["clientes"]),
            "dias_acumulado_mediana": float(row["dias_acumulado_mediana"]),
            "dias_acumulado_media": float(row["dias_acumulado_media"]),
            "dias_entre_recompras_mediana": float(row["dias_entre_recompras_mediana"]),
            "dias_entre_recompras_media": float(row["dias_entre_recompras_media"]),
        })
    return registros


def montar_fact_arvore() -> list[dict]:
    n_clientes_por_entrada = {row["entrada"]: int(row["clientes"]) for row in _ler_csv("ltv_por_entrada.csv")}
    with open(SAIDA_LOCAL_DIR / "arvore_jornada.json", encoding="utf-8") as arquivo:
        arvores = json.load(arquivo)

    registros = []
    for entrada, arvore in arvores.items():
        registros.append({
            "entrada": entrada,
            "n_clientes": n_clientes_por_entrada[entrada],
            "arvore": arvore,
        })
    return registros
