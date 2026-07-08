"""Gera um relatorio Markdown portavel (sem HTML/JS) a partir de resultado_plinko.json,
para o Daniel compartilhar com outra IA analisar junto. Roda depois de analise_plinko.py."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(HERE, "resultado_plinko.json")
OUTPUT_MD = os.path.join(HERE, "Relatorio_Efeito_Plinko_Fase1.md")

SEG_LABEL = {
    "geral": "Geral (Primeira Compra + Recompra)",
    "primeira_compra": "Primeira Compra",
    "recompra": "Recompra",
}


def fmt_int(n):
    return f"{n:,.0f}".replace(",", ".")


def fmt_pct(n):
    if n is None:
        return "-"
    return f"{n:.1f}%".replace(".", ",")


def fmt_dias(n):
    if n is None:
        return "-"
    return f"{n:.1f}d".replace(".", ",")


def fmt_brl(n):
    return "R$ " + f"{n:,.0f}".replace(",", ".")


def hist_table(hist):
    header = "| " + " | ".join(hist.keys()) + " |"
    sep = "|" + "|".join(["---"] * len(hist)) + "|"
    row = "| " + " | ".join(fmt_int(v) for v in hist.values()) + " |"
    return f"{header}\n{sep}\n{row}"


def canal_fecha_table(dct, total):
    lines = ["| Canal que fecha | Pedidos | % |", "|---|---:|---:|"]
    for canal, n in dct.items():
        lines.append(f"| {canal} | {fmt_int(n)} | {fmt_pct(100 * n / total)} |")
    return "\n".join(lines)


def group_block(title, dado):
    lines = [f"#### {title}", ""]
    lines.append(f"- Pedidos: **{fmt_int(dado['n_pedidos'])}** ({fmt_pct(dado['pct_do_total_de_vendas'])} do total de vendas do segmento)")
    lines.append(f"- Receita associada: {fmt_brl(dado['receita_associada'])}")
    p = dado["dias_ate_compra"]
    lines.append(f"- Tempo até compra — mediana {fmt_dias(p['mediana'])} | P50 {fmt_dias(p['p50'])} | P80 {fmt_dias(p['p80'])} | P90 {fmt_dias(p['p90'])}")
    lines.append(f"- % dos pedidos SEM nenhum outro toque no meio (venda direta): {fmt_pct(dado['pct_sem_toque_no_meio'])}")
    lines.append(f"- % que fecha pelo MESMO canal do toque analisado: {fmt_pct(dado['pct_fechou_mesmo_canal'])}")
    lines.append(f"- Média de touchpoints de outros canais no meio: {dado['qtd_touchpoints_entre_media']}")
    lines.append("")
    lines.append("Histograma de dias até a compra (contagem de pedidos por faixa):")
    lines.append("")
    lines.append(hist_table(dado["histograma_dias"]))
    lines.append("")
    lines.append("Distribuição de quem fecha a venda:")
    lines.append("")
    lines.append(canal_fecha_table(dado["canal_que_fecha"], dado["n_pedidos"]))
    lines.append("")
    return "\n".join(lines)


def fluxo_table(fluxos, top_n=15):
    entries = sorted(fluxos.items(), key=lambda kv: -kv[1]["n_pedidos"])
    top = entries[:top_n]
    resto = entries[top_n:]
    resto_n = sum(dado["n_pedidos"] for _, dado in resto)
    lines = [
        "| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, dado in top:
        flag = "*(nao mapeado)* " if (name.startswith("Nao mapeado") or name.startswith("Ambiguo")) else ""
        lines.append(
            f"| {flag}{name} | {fmt_int(dado['n_pedidos'])} | {fmt_pct(dado['pct_do_total_de_vendas'])} | "
            f"{fmt_dias(dado['dias_ate_compra']['mediana'])} | {fmt_dias(dado['dias_ate_compra']['p80'])} | "
            f"{fmt_pct(dado['pct_sem_toque_no_meio'])} | {fmt_pct(dado['pct_fechou_mesmo_canal'])} | "
            f"{fmt_brl(dado['receita_associada'])} |"
        )
    table = "\n".join(lines)
    if resto:
        table += f"\n\n*+ {len(resto)} outros fluxos menores, somando {fmt_int(resto_n)} pedidos (omitidos aqui por volume baixo).*"
    return table


def main() -> None:
    with open(INPUT_JSON, encoding="utf-8") as f:
        d = json.load(f)

    out = []
    out.append("# Relatorio — Efeito Plinko na Atribuicao de Reativacao (Fase 1)")
    out.append("")
    out.append(f"Gerado em {d['gerado_em']} · Minimal Club · Dashboard CRM")
    out.append("")
    out.append("## 1. Contexto e pergunta")
    out.append(
        "\nHoje, quando um e-mail ou WhatsApp de reativacao e disparado, ele costuma ser avaliado so pela "
        "receita que o Klaviyo/Vekta atribuem via **last-click direto** (o clique que efetivamente fechou a "
        "venda). Isso subestima o efeito real, porque esse toque raramente fecha a venda sozinho — ele "
        "\"acorda\" o cliente, que depois passa por outros canais (Meta, Google, direto, organico, outro "
        "e-mail, outro WhatsApp) antes de comprar.\n\n"
        "Essa analise (Fase 1) mede, usando dados reais de pedidos pagos, o que acontece quando um toque de "
        "e-mail ou WhatsApp aparece **no meio do caminho** de uma compra — ou seja, quando nao e o ultimo "
        "clique antes dela:\n\n"
        "1. Que % de todas as vendas esse canal/fluxo tocou (nao como ultimo clique)?\n"
        "2. Quanto tempo depois desse toque a compra realmente aconteceu (distribuicao completa, nao so a "
        "media)?\n"
        "3. Quantos outros toques aparecem no meio (evidencia de \"cascata\" entre canais)?\n"
        "4. Quem efetivamente fecha a venda, quando nao e o proprio canal analisado?\n"
    )

    out.append("## 2. Fonte de dados e limitacoes (importante para interpretar os numeros)")
    out.append(
        f"\n- **Fonte:** `Base de Touchpoints.csv`, export nativo do Shopify (nao e um pixel/CDP de eventos "
        "brutos). Cada linha e uma **sessao de entrada no site** cujo UTM foi o **last-click daquela sessao** "
        "— nao um log de todo micro-evento (abertura de e-mail, impressao de anuncio etc.).\n"
        f"- **Escopo:** somente pedidos com `financial_status = PAID`. {fmt_int(d['stats_carregamento']['total_orders'])} "
        f"pedidos pagos no periodo (aprox. maio–julho/2026). Divididos em "
        f"{fmt_int(d['orders_by_segment']['primeira_compra'])} de Primeira Compra e "
        f"{fmt_int(d['orders_by_segment']['recompra'])} de Recompra.\n"
        "- **Janela de atribuicao:** cada pedido so carrega os touchpoints dos ~30 dias antes da compra — nao "
        "e um historico completo de interacao do cliente. Um toque de reativacao que aconteceu mais de 30 "
        "dias antes da compra nao aparece nesta base.\n"
        "- **Sem gate de \"cliente frio\" ainda** (Fase 2, futura): nao ha verificacao de inatividade previa "
        "(90/180/365 dias sem comprar/clicar) antes de considerar um toque como \"de reativacao\" — todo "
        "toque de e-mail/WhatsApp que nao e o ultimo clique conta aqui, mesmo que o cliente ja estivesse "
        "\"quente\". Isso e um vies conservador: o efeito real de reativacao pura tende a ser tao forte ou "
        "mais forte que o mostrado aqui.\n"
        "- **Classificacao de canal:** baseada no `utm_medium` real observado nos dados (nao na tabela "
        "idealizada do banco) — ver mapeamento na Secao 6.\n"
        f"- **{fmt_int(d['total_eventos_qualificados'])} eventos qualificados** (toques de CRM no meio do "
        "caminho) foram analisados no total, cobrindo os 3 recortes abaixo.\n"
    )

    for idx, seg_key in enumerate(["geral", "primeira_compra", "recompra"], start=1):
        seg = d["segments"][seg_key]
        out.append(f"## 3.{idx}. Segmento: {SEG_LABEL[seg_key]}")
        out.append("")
        out.append(f"**Total de pedidos pagos neste segmento:** {fmt_int(seg['total_orders'])}")
        out.append(
            f"**Pedidos com QUALQUER toque de CRM (e-mail e/ou WhatsApp) no meio do caminho:** "
            f"{fmt_int(seg['pedidos_tocados_crm'])} ({fmt_pct(seg['pct_pedidos_tocados_crm'])} do total) — "
            f"receita associada: {fmt_brl(seg['receita_tocada_crm'])}"
        )
        out.append("")
        out.append("### Nivel 1 — Canal completo (E-mail vs. WhatsApp)")
        out.append("")
        r = seg["relatorio"]["nivel_1_macro"]
        out.append(group_block("E-mail", r["E-mail"]))
        out.append(group_block("WhatsApp", r["WhatsApp"]))

        out.append("### Nivel 2 — Os 5 canais oficiais (resumo)")
        out.append("")
        n2 = seg["relatorio"]["nivel_2_canal"]
        lines = [
            "| Canal | Pedidos | % do total | Mediana | P80 | P90 | Sem toque no meio | Fecha mesmo canal | Receita |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for canal, dado in n2.items():
            p = dado["dias_ate_compra"]
            lines.append(
                f"| {canal} | {fmt_int(dado['n_pedidos'])} | {fmt_pct(dado['pct_do_total_de_vendas'])} | "
                f"{fmt_dias(p['mediana'])} | {fmt_dias(p['p80'])} | {fmt_dias(p['p90'])} | "
                f"{fmt_pct(dado['pct_sem_toque_no_meio'])} | {fmt_pct(dado['pct_fechou_mesmo_canal'])} | "
                f"{fmt_brl(dado['receita_associada'])} |"
            )
        out.append("\n".join(lines))
        out.append("")

        out.append("### Nivel 3 — Fluxos individuais (top 15 por volume)")
        out.append("")
        n3 = seg["relatorio"]["nivel_3_fluxo"]
        out.append("**E-mail Fluxo:**")
        out.append("")
        out.append(fluxo_table(n3["E-mail Fluxo"]))
        out.append("")
        out.append("**WhatsApp Fluxo:**")
        out.append("")
        out.append(fluxo_table(n3["WhatsApp Fluxo"]))
        out.append("")

    out.append("## 4. Campanhas/fluxos nao mapeados (gap de configuracao)")
    out.append(
        "\nToda campanha/termo de UTM que apareceu nos dados mas nao bate com a planilha "
        "`configuracoes de utm.xlsx` (e-mail) nem com as tabelas `dim_wpp_origem_mapping`/"
        "`dim_wpp_alia_campanha_mapping` do Supabase (WhatsApp). Reportado em vez de descartado.\n"
    )
    lines = ["| Campanha/termo (raw) | Ocorrencias |", "|---|---:|"]
    for name, n in d["nao_mapeados"].items():
        lines.append(f"| {name} | {fmt_int(n)} |")
    out.append("\n".join(lines))
    out.append("")
    out.append(
        "**Maiores gaps:** `abandoned_cart_ia` (fluxo de recuperacao de carrinho via IA, ~1.841 pedidos "
        "somando e-mail e WhatsApp) e `cartstack` (ferramenta de terceiro, ~742 pedidos) nao existem em "
        "nenhuma referencia cadastrada — vale adicionar antes da Fase 2."
    )
    out.append("")

    out.append("## 5. Achados principais (sintese)")
    out.append(
        "\n1. **Efeito Plinko confirmado mesmo sem gate de cliente frio:** so ~31% dos pedidos tocados por "
        "e-mail no meio do caminho fecham pelo proprio e-mail (~35% no WhatsApp) — a maior fatia fecha por "
        "\"Outro\" (Meta/Google/direto/organico).\n"
        "2. **Recompra e tocada quase 2x mais que Primeira Compra:** 20,9% dos pedidos de recompra tiveram "
        "toque de CRM no meio, contra 11,4% na primeira compra — o efeito Plinko pesa mais na regua de "
        "recompra.\n"
        "3. **WhatsApp reativa mais rapido que e-mail:** mediana de 1,3 dia vs. 3,9 dias ate a compra (visao "
        "geral).\n"
        "4. **Gaps de configuracao de UTM** (Secao 4) escondem parte do volume real de dois fluxos de alto "
        "volume.\n"
    )

    out.append("## 6. Regras de classificacao usadas (para auditoria)")
    out.append(
        "\n| Canal oficial | utm_medium considerado (case-insensitive) |\n"
        "|---|---|\n"
        "| E-mail Fluxo | `email_fluxo`, `fluxos_crm` |\n"
        "| E-mail Campanha | `email_campanha` |\n"
        "| WhatsApp Fluxo | `whatsapp_fluxo`, `whatsapp_fluxo_ia` |\n"
        "| WhatsApp Campanha | `whatsapp_campanha` |\n"
        "| WhatsApp Comunidade | `comunidade` |\n\n"
        "Um \"toque de reativacao\" = touchpoint com um desses `utm_medium`, que NAO e o ultimo clique antes "
        "da compra (`is_last_before_purchase = false`). \"Dias ate a compra\" = `processed_at` (data/hora da "
        "compra) menos `touchpoint_at` (data/hora desse toque especifico). Quando um pedido tem mais de um "
        "toque qualificado do mesmo tipo, usa-se o primeiro cronologicamente (e o que \"soltou a ficha\")."
    )

    report = "\n".join(out)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Escrito: {OUTPUT_MD} - {len(report)} caracteres")


if __name__ == "__main__":
    main()
