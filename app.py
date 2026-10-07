import json

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

TITULO = "Mapa Interativo de Votação - Raphael Mota"
ARQUIVO_DADOS = "dados_mg.geojson"
SEM_VOTO = "#e6e6e6"

st.set_page_config(page_title=TITULO, page_icon="🗳️", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 3.5rem; max-width: 1200px;}
    .titulo {font-size: 2.2rem; font-weight: 800; color: #1f3a93; line-height: 1.2;}
    .subtitulo {color: #555; font-size: 1.05rem; margin: .3rem 0 1.4rem 0;}
    .secao {font-size: 1.4rem; font-weight: 700; color: #1f3a93; line-height: 1.3;
            border-bottom: 3px solid #f2b705; padding-bottom: .3rem; margin: 2rem 0 1rem 0;}
    div[data-testid="stMetricValue"] {color: #1f3a93;}
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_int(n):
    return f"{int(n):,}".replace(",", ".")


def fmt_pct(x):
    return f"{x:.2f}".replace(".", ",") + "%"


def fmt_dec(x):
    return f"{x:.2f}".replace(".", ",")


@st.cache_data
def carregar():
    with open(ARQUIVO_DADOS, encoding="utf-8") as f:
        gj = json.load(f)
    for ft in gj["features"]:
        p = ft["properties"]
        p["votos_fmt"] = fmt_int(p["votos"])
        p["pct_fmt"] = fmt_pct(p["pct_validos"])
        p["posicao_fmt"] = f"{p['posicao']}º" if p["votos"] > 0 else "sem votos"
    df = pd.DataFrame([ft["properties"] for ft in gj["features"]])
    return gj, df


def limites(features):
    xs, ys = [], []

    def percorrer(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for item in c:
                percorrer(item)

    for ft in features:
        percorrer(ft["geometry"]["coordinates"])
    return [[min(ys), min(xs)], [max(ys), max(xs)]]


def escala(df, coluna, legenda):
    valores = df.loc[df["votos"] > 0, coluna]
    cortes = sorted(set(valores.quantile([i / 7 for i in range(8)]).round(4).tolist()))
    if len(cortes) < 2:
        cortes = [0, float(valores.max() or 1)]
    cores = cm.linear.YlOrRd_09.scale(cortes[0], cortes[-1]).to_step(index=cortes)
    cores.caption = legenda
    return cores


def montar_mapa(gj, df, coluna, legenda, destaque=None, altura_zoom=None):
    cores = escala(df, coluna, legenda)
    destaque = set(destaque or [])
    m = folium.Map(tiles=None, zoom_control=True, prefer_canvas=True)

    def estilo(ft):
        p = ft["properties"]
        selecionado = p["nome"] in destaque
        return {
            "fillColor": cores(p[coluna]) if p["votos"] > 0 else SEM_VOTO,
            "color": "#1f3a93" if selecionado else "white",
            "weight": 3 if selecionado else 0.4,
            "fillOpacity": 0.9,
        }

    folium.GeoJson(
        gj,
        style_function=estilo,
        highlight_function=lambda ft: {"weight": 2.5, "color": "#1f3a93"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nome", "votos_fmt", "pct_fmt", "posicao_fmt"],
            aliases=["Município", "Votos", "% dos válidos", "Posição"],
            sticky=True,
        ),
    ).add_to(m)
    cores.add_to(m)

    if destaque:
        feats = [ft for ft in gj["features"] if ft["properties"]["nome"] in destaque]
        m.fit_bounds(limites(feats), padding=(40, 40))
    else:
        m.fit_bounds(limites(gj["features"]))
    return m


gj, df = carregar()
com_voto = df[df["votos"] > 0].sort_values("votos", ascending=False)
total_votos = int(df["votos"].sum())
total_validos = df["validos"].sum()

# ===== CABEÇALHO =====
st.markdown(f'<div class="titulo">{TITULO}</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitulo">Deputado Federal · 1038 · Republicanos · Minas Gerais · 1º turno 2026</div>',
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de votos", fmt_int(total_votos))
k2.metric("Municípios com voto", f"{len(com_voto)} de {len(df)}")
k3.metric("% dos válidos em MG", fmt_pct(100 * total_votos / total_validos) if total_validos else "-")
k4.metric("Maior votação", com_voto.iloc[0]["nome"] if len(com_voto) else "-")

# ===== 1. MAPA =====
st.markdown('<div class="secao">Mapa de votação</div>', unsafe_allow_html=True)
metrica = st.radio(
    "Colorir o mapa por:",
    ["% dos votos válidos", "Votos absolutos"],
    horizontal=True,
    help="% dos válidos mostra a força relativa em cada município. Votos absolutos destaca as cidades maiores.",
)
coluna = "pct_validos" if metrica.startswith("%") else "votos"
st_folium(
    montar_mapa(gj, df, coluna, metrica),
    height=620,
    use_container_width=True,
    returned_objects=[],
    key="mapa_geral",
)
st.caption("Cinza: municípios sem votos. Passe o dedo ou o mouse sobre um município para ver os números.")

# ===== 2. TOP 20 =====
st.markdown('<div class="secao">Top 20 municípios com mais votos</div>', unsafe_allow_html=True)
top20 = com_voto.head(20)
tabela_top = pd.DataFrame({
    "Posição": top20["posicao"].astype(int),
    "Município": top20["nome"],
    "Votos": top20["votos"].astype(int),
    "% dos válidos": top20["pct_validos"].map(fmt_pct),
    "Votos por mil eleitores": top20["votos_mil"].map(fmt_dec),
})
st.dataframe(
    tabela_top,
    hide_index=True,
    width="stretch",
    height=36 * 21 + 3,
    column_config={
        "Votos": st.column_config.ProgressColumn(
            "Votos", format="%d", min_value=0, max_value=int(top20["votos"].max()) if len(top20) else 1
        ),
    },
)
st.caption(f"Os 20 primeiros somam {fmt_int(top20['votos'].sum())} votos, "
           f"{fmt_pct(100 * top20['votos'].sum() / total_votos) if total_votos else '-'} do total.")

# ===== 3. CONSULTA POR MUNICÍPIO =====
st.markdown('<div class="secao">Consultar por município</div>', unsafe_allow_html=True)
escolhidos = st.multiselect(
    "Digite o nome de um ou mais municípios",
    options=sorted(df["nome"].tolist()),
    placeholder="Ex.: Ouro Branco",
)

if escolhidos:
    sel = df[df["nome"].isin(escolhidos)].sort_values("votos", ascending=False)
    if len(sel) == 1:
        p = sel.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Votos", fmt_int(p["votos"]))
        c2.metric("Posição no ranking", f"{int(p['posicao'])}º de {len(com_voto)}" if p["votos"] > 0 else "sem votos")
        c3.metric("% dos válidos", fmt_pct(p["pct_validos"]))
        c4.metric("Votos por mil eleitores", fmt_dec(p["votos_mil"]))
    else:
        c1, c2 = st.columns(2)
        c1.metric("Votos nos municípios selecionados", fmt_int(sel["votos"].sum()))
        c2.metric("Participação no total", fmt_pct(100 * sel["votos"].sum() / total_votos) if total_votos else "-")

    st.dataframe(
        pd.DataFrame({
            "Município": sel["nome"],
            "Posição": sel.apply(lambda r: f"{int(r['posicao'])}º" if r["votos"] > 0 else "sem votos", axis=1),
            "Votos": sel["votos"].map(fmt_int),
            "% dos válidos": sel["pct_validos"].map(fmt_pct),
            "Eleitores aptos": sel["aptos"].map(fmt_int),
            "Votos por mil eleitores": sel["votos_mil"].map(fmt_dec),
        }),
        hide_index=True,
        width="stretch",
    )
    st_folium(
        montar_mapa(gj, df, coluna, metrica, destaque=escolhidos),
        height=450,
        use_container_width=True,
        returned_objects=[],
        key="mapa_consulta",
    )

with st.expander("Ver ranking completo e baixar planilha"):
    completo = pd.DataFrame({
        "Posição": com_voto["posicao"].astype(int),
        "Município": com_voto["nome"],
        "Votos": com_voto["votos"].astype(int),
        "% dos válidos": com_voto["pct_validos"].round(3),
        "Eleitores aptos": com_voto["aptos"].astype(int),
        "Votos por mil eleitores": com_voto["votos_mil"].round(2),
    })
    st.dataframe(completo, hide_index=True, width="stretch")
    st.download_button(
        "Baixar ranking (CSV)",
        completo.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name="ranking_raphael_mota_1038_MG_1t2026.csv",
        mime="text/csv",
    )

st.caption("Fonte: TSE, Boletim de Urna do 1º turno de 2026 (Portal de Dados Abertos). Malha municipal: IBGE.")
