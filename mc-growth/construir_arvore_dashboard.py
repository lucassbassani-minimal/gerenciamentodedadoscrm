"""Reconstroi a arvore de jornada (drill-down 2a->5a compra) usando a classificacao
EXCLUSIVA de produto ja corrigida em sequencia_compras_detalhe.csv (coluna `produto`,
gerada por jornada_produto.py) - a versao anterior de arvore_jornada.json era de ANTES
dos bugs de aliasing/contagem serem corrigidos, entao fica obsoleta. So para o proposito
de visualizacao (arvore); a analise "o que ofertar" continua usando afinidade por
presenca (afinidade_produtos.csv), nao esta arvore. Roda local, saida vai pro Supabase
via ingestion/analytics/jornada_produto_ingest.py."""

import json

import pandas as pd

PROFUNDIDADE_MAX = 5
TOP_N = 3
N_MINIMO = 30


def construir_no(seq_entrada: pd.DataFrame, clientes: set, pos: int) -> list[dict]:
    n_pai = len(clientes)
    if n_pai == 0:
        return []

    no_pai = seq_entrada[(seq_entrada["posicao"] == pos) & seq_entrada["e_mail"].isin(clientes)]
    grupos = no_pai.groupby("produto")["e_mail"].apply(set).to_dict()
    ordenado = sorted(grupos.items(), key=lambda kv: len(kv[1]), reverse=True)

    chegaram: set = set().union(*grupos.values()) if grupos else set()
    nao_voltou = clientes - chegaram

    filhos = []
    for produto, emails in ordenado[:TOP_N]:
        n = len(emails)
        no = {"produto": produto, "clientes": n, "pct_do_pai": round(n / n_pai * 100, 1)}
        if pos < PROFUNDIDADE_MAX and n >= N_MINIMO:
            no["filhos"] = construir_no(seq_entrada, emails, pos + 1)
        filhos.append(no)

    resto = set().union(*(e for _p, e in ordenado[TOP_N:])) if len(ordenado) > TOP_N else set()
    if resto:
        filhos.append({"produto": "Outros produtos", "clientes": len(resto),
                       "pct_do_pai": round(len(resto) / n_pai * 100, 1)})
    if nao_voltou:
        filhos.append({"produto": "Não comprou de novo", "clientes": len(nao_voltou),
                       "pct_do_pai": round(len(nao_voltou) / n_pai * 100, 1)})
    return filhos


def rodar():
    seq = pd.read_csv("saida_local/sequencia_compras_detalhe.csv")
    seq_pos = seq[seq["posicao"].between(2, PROFUNDIDADE_MAX)]

    entradas = seq[seq["posicao"] == 1].groupby("entrada")["e_mail"].nunique().sort_values(ascending=False)
    arvores = {}
    for entrada in entradas.index:
        clientes_entrada = set(seq.loc[(seq.entrada == entrada) & (seq.posicao == 1), "e_mail"])
        seq_entrada = seq_pos[seq_pos["e_mail"].isin(clientes_entrada)]
        arvores[entrada] = construir_no(seq_entrada, clientes_entrada, pos=2)

    with open("saida_local/arvore_jornada.json", "w", encoding="utf-8") as f:
        json.dump(arvores, f, ensure_ascii=False)
    print(f"{len(arvores)} arvores reconstruidas (pipeline corrigido)")


if __name__ == "__main__":
    rodar()
