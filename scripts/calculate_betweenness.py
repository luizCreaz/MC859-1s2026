"""
Cálculo do Betweenness Centrality para os Grafos de Municípios de Minas Gerais.

O betweenness centrality de um vértice v é a fração dos menores caminhos entre
todos os pares de vértices que passam por v:

    BC(v) = Σ_{s≠v≠t} σ(s,t|v) / σ(s,t)

onde σ(s,t) é o número total de menores caminhos de s a t, e σ(s,t|v) é o
número desses caminhos que passam por v.

O NetworkX normaliza pelo número de pares possíveis: (n-1)(n-2)/2 para grafos
não-direcionados, de modo que BC ∈ [0, 1].

Municípios com BC alto funcionam como "pontes" ou "entroncamentos" na rede,
conectando regiões distantes. Este script também correlaciona o BC com a taxa
de feminicídio para investigar se municípios mais centrais apresentam taxas
diferentes dos periféricos.

Dependências:
    pip install networkx scipy numpy pandas matplotlib tqdm

Uso:
    python calculate_betweenness.py [--graphml-ibge <path>] [--graphml-geofabrik <path>]
                                    [--k <amostragem>] [--seed <semente>]

    --k: número de vértices amostrados para aproximação (None = exato, porém lento).
         Para 853 vértices, o cálculo exato costuma terminar em < 5 minutos.
"""

import argparse
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats


# ---------------------------------------------------------------------------
# 1. Carregamento do grafo
# ---------------------------------------------------------------------------

def carregar_grafo(caminho: str | Path) -> nx.Graph:
    """Carrega um grafo a partir de um arquivo GraphML."""
    caminho = Path(caminho)
    if not caminho.exists():
        print(f"[ERRO] Arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    print(f"Carregando grafo de: {caminho}")
    G = nx.read_graphml(caminho)

    # Converte atributos numéricos (podem vir como string no GraphML)
    for node, data in G.nodes(data=True):
        for chave in ("taxa_feminicidio_norm", "lat", "lon"):
            val = data.get(chave)
            if val is not None:
                try:
                    G.nodes[node][chave] = float(val)
                except (ValueError, TypeError):
                    pass

    return G


# ---------------------------------------------------------------------------
# 2. Cálculo do Betweenness Centrality
# ---------------------------------------------------------------------------

def calcular_betweenness(G: nx.Graph,
                          k: int | None = None,
                          seed: int = 42,
                          peso: str | None = None) -> dict:
    """
    Calcula o betweenness centrality para todos os vértices do grafo.

    Parâmetros
    ----------
    G    : grafo NetworkX (não-direcionado)
    k    : se None, cálculo exato O(VE); se inteiro, aproximação por amostragem
           de k vértices fonte (recomendado para grafos muito grandes)
    seed : semente para reprodutibilidade na amostragem
    peso : nome do atributo de aresta a usar como peso (None = sem peso / BFS)

    Retorna
    -------
    dict com os valores de BC por vértice e estatísticas descritivas
    """
    n = G.number_of_nodes()
    m = G.number_of_edges()

    if k is None:
        print(f"  Calculando BC exato para {n} vértices e {m} arestas ...")
        print(f"  (Complexidade O(VE) ≈ {n * m:,} operações — pode levar alguns minutos)")
    else:
        print(f"  Calculando BC aproximado (k={k} amostras) para {n} vértices ...")

    bc = nx.betweenness_centrality(G, k=k, normalized=True,
                                    weight=peso, seed=seed)

    valores = np.array(list(bc.values()))
    return {
        "bc":         bc,           # dict: node -> BC value
        "valores":    valores,
        "min":        float(valores.min()),
        "max":        float(valores.max()),
        "media":      float(valores.mean()),
        "mediana":    float(np.median(valores)),
        "desvio":     float(valores.std()),
        "percentil_90": float(np.percentile(valores, 90)),
        "percentil_95": float(np.percentile(valores, 95)),
        "percentil_99": float(np.percentile(valores, 99)),
    }


# ---------------------------------------------------------------------------
# 3. Correlação BC × taxa de feminicídio
# ---------------------------------------------------------------------------

def correlacionar_bc_taxa(G: nx.Graph, bc: dict,
                           atributo: str = "taxa_feminicidio_norm") -> dict:
    """
    Correlaciona o betweenness centrality com o atributo numérico de cada vértice.

    Usa tanto Pearson (sensível a outliers) quanto Spearman (baseada em postos,
    mais robusta para distribuições assimétricas como o BC).
    """
    pares = []
    for node, data in G.nodes(data=True):
        taxa = data.get(atributo)
        bc_v = bc.get(node)
        if taxa is None or bc_v is None:
            continue
        if isinstance(taxa, float) and np.isnan(taxa):
            continue
        pares.append((float(taxa), float(bc_v)))

    if len(pares) < 10:
        print("[AVISO] Poucos pares válidos para correlação.")
        return {}

    taxa_arr = np.array([p[0] for p in pares])
    bc_arr   = np.array([p[1] for p in pares])

    pearson_r,  pearson_p  = stats.pearsonr(bc_arr, taxa_arr)
    spearman_r, spearman_p = stats.spearmanr(bc_arr, taxa_arr)

    return {
        "n_pares":        len(pares),
        "taxa_arr":        taxa_arr,
        "bc_arr":          bc_arr,
        "pearson_r":       float(pearson_r),
        "pearson_p":       float(pearson_p),
        "spearman_r":      float(spearman_r),
        "spearman_p":      float(spearman_p),
    }


# ---------------------------------------------------------------------------
# 4. Top municípios por BC
# ---------------------------------------------------------------------------

def top_municipios(G: nx.Graph, bc: dict, n: int = 20) -> pd.DataFrame:
    """Retorna os n municípios com maior betweenness centrality."""
    rows = []
    for node, bc_val in bc.items():
        data = G.nodes[node]
        rows.append({
            "municipio":             data.get("name", node),
            "geocodigo":             data.get("geocodigo", node),
            "betweenness_centrality": bc_val,
            "taxa_feminicidio_norm":  data.get("taxa_feminicidio_norm"),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("betweenness_centrality", ascending=False).head(n)
    df = df.reset_index(drop=True)
    df.index += 1
    return df


# ---------------------------------------------------------------------------
# 5. Visualizações
# ---------------------------------------------------------------------------

def plotar_distribuicao_bc(valores: np.ndarray, titulo: str,
                            caminho_saida: str | Path | None = None):
    """Histograma + boxplot do BC."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Histograma
    ax = axes[0]
    ax.hist(valores, bins=50, color="#2b7bba", edgecolor="white", alpha=0.85)
    ax.axvline(valores.mean(), color="red",    linestyle="--", label=f"Média = {valores.mean():.4f}")
    ax.axvline(np.median(valores), color="orange", linestyle=":", label=f"Mediana = {np.median(valores):.4f}")
    ax.set_xlabel("Betweenness Centrality (normalizado)", fontsize=11)
    ax.set_ylabel("Frequência", fontsize=11)
    ax.set_title(f"Distribuição do BC\n{titulo}", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Boxplot
    ax = axes[1]
    bp = ax.boxplot(valores, vert=True, patch_artist=True,
                    boxprops=dict(facecolor="#2b7bba", alpha=0.7))
    ax.set_ylabel("Betweenness Centrality (normalizado)", fontsize=11)
    ax.set_title(f"Boxplot do BC\n{titulo}", fontsize=11)
    ax.set_xticks([])
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    if caminho_saida:
        caminho_saida = Path(caminho_saida)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
        print(f"  Distribuição BC salva em: {caminho_saida}")
    plt.show()
    plt.close()


def plotar_correlacao_bc_taxa(corr: dict, titulo: str,
                               caminho_saida: str | Path | None = None):
    """Scatter BC × taxa de feminicídio com linha de tendência."""
    bc_arr   = corr["bc_arr"]
    taxa_arr = corr["taxa_arr"]
    pr       = corr["pearson_r"]
    pp       = corr["pearson_p"]
    sr       = corr["spearman_r"]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(bc_arr, taxa_arr, alpha=0.4, s=12, color="#2b7bba", edgecolors="none")

    # Linha de tendência
    if len(bc_arr) > 2:
        m, b = np.polyfit(bc_arr, taxa_arr, 1)
        xmin, xmax = bc_arr.min(), bc_arr.max()
        ax.plot([xmin, xmax], [m * xmin + b, m * xmax + b],
                color="red", linewidth=1.5)

    ax.set_xlabel("Betweenness Centrality (normalizado)", fontsize=11)
    ax.set_ylabel("Taxa de feminicídio (normalizada)", fontsize=11)
    ax.set_title(
        f"{titulo}\n"
        f"Pearson r = {pr:.4f} (p = {pp:.2e})  |  Spearman r = {sr:.4f}",
        fontsize=11
    )
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if caminho_saida:
        caminho_saida = Path(caminho_saida)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
        print(f"  Scatter BC×taxa salvo em: {caminho_saida}")
    plt.show()
    plt.close()


def plotar_top_municipios(df_top: pd.DataFrame, titulo: str,
                           caminho_saida: str | Path | None = None):
    """Gráfico de barras horizontais dos municípios com maior BC."""
    fig, ax = plt.subplots(figsize=(10, 6))

    cores = ["#d62728" if t is not None and t > 0.5 else "#2b7bba"
             for t in df_top["taxa_feminicidio_norm"]]
    ax.barh(df_top["municipio"][::-1], df_top["betweenness_centrality"][::-1],
            color=cores[::-1], edgecolor="white", alpha=0.85)

    ax.set_xlabel("Betweenness Centrality (normalizado)", fontsize=11)
    ax.set_title(f"Top municípios — Betweenness Centrality\n{titulo}", fontsize=11)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#d62728", label="Taxa feminicídio > 0.5"),
        Patch(facecolor="#2b7bba", label="Taxa feminicídio ≤ 0.5"),
    ]
    ax.legend(handles=legend_elements, fontsize=9, loc="lower right")
    ax.grid(True, alpha=0.3, axis="x")
    plt.tight_layout()

    if caminho_saida:
        caminho_saida = Path(caminho_saida)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
        print(f"  Top municípios salvo em: {caminho_saida}")
    plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# 6. Exportação dos resultados
# ---------------------------------------------------------------------------

def exportar_csv(G: nx.Graph, bc: dict,
                  caminho: str | Path = "../data/results/betweenness_centrality.csv"):
    """
    Salva um CSV com BC e demais atributos de cada município.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for node, data in G.nodes(data=True):
        rows.append({
            "node_id":                node,
            "municipio":              data.get("name", ""),
            "geocodigo":              data.get("geocodigo", ""),
            "betweenness_centrality": bc.get(node, float("nan")),
            "taxa_feminicidio_norm":  data.get("taxa_feminicidio_norm"),
            "grau":                   G.degree(node),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("betweenness_centrality", ascending=False)
    df["rank_bc"] = range(1, len(df) + 1)
    df.to_csv(caminho, index=False, float_format="%.8f")
    print(f"\n  CSV exportado: {caminho}  ({len(df)} linhas)")
    return df


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Calcula o Betweenness Centrality dos grafos de municípios de MG."
    )
    parser.add_argument(
        "--graphml-ibge",
        default="../data/graphs/grafo_mg_adjacencia.graphml",
        help="Caminho para o GraphML do grafo IBGE (fronteiras físicas)."
    )
    parser.add_argument(
        "--graphml-geofabrik",
        default="../data/graphs/grafo_mg_rodoviario.graphml",
        help="Caminho para o GraphML do grafo Geofabrik (rodovias)."
    )
    parser.add_argument(
        "--k", type=int, default=None,
        help="Número de vértices para aproximação do BC (None = exato)."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Semente aleatória para reprodutibilidade (usado quando --k é definido)."
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Quantos municípios exibir no ranking."
    )
    parser.add_argument(
        "--sem-plots", action="store_true",
        help="Não exibe/salva gráficos."
    )
    args = parser.parse_args()

    grafos = {
        "ibge":       ("IBGE (fronteiras físicas)",  args.graphml_ibge),
        "geofabrik":  ("Geofabrik (rodovias)",       args.graphml_geofabrik),
    }

    for slug, (nome, caminho) in grafos.items():
        print("\n" + "=" * 60)
        print(f"  Grafo: {nome}")
        print("=" * 60)

        G = carregar_grafo(caminho)

        # --- Cálculo do BC ---
        res_bc = calcular_betweenness(G, k=args.k, seed=args.seed)
        bc     = res_bc["bc"]

        # Estatísticas
        print(f"\n  --- Estatísticas do Betweenness Centrality ---")
        print(f"  Vértices : {G.number_of_nodes()}")
        print(f"  Arestas  : {G.number_of_edges()}")
        print(f"  BC mín   : {res_bc['min']:.8f}")
        print(f"  BC máx   : {res_bc['max']:.8f}")
        print(f"  BC média : {res_bc['media']:.8f}")
        print(f"  BC mediana: {res_bc['mediana']:.8f}")
        print(f"  BC desvio: {res_bc['desvio']:.8f}")
        print(f"  Percentil 90/95/99: {res_bc['percentil_90']:.6f} / "
              f"{res_bc['percentil_95']:.6f} / {res_bc['percentil_99']:.6f}")

        # --- Top municípios ---
        df_top = top_municipios(G, bc, n=args.top)
        print(f"\n  --- Top {args.top} municípios por BC ---")
        print(df_top[["municipio", "betweenness_centrality",
                       "taxa_feminicidio_norm"]].to_string())

        # --- Correlação BC × taxa ---
        corr = correlacionar_bc_taxa(G, bc)
        if corr:
            print(f"\n  --- Correlação BC × taxa de feminicídio ---")
            print(f"  N pares válidos : {corr['n_pares']}")
            print(f"  Pearson  r = {corr['pearson_r']:.6f}  (p = {corr['pearson_p']:.4e})")
            print(f"  Spearman r = {corr['spearman_r']:.6f}  (p = {corr['spearman_p']:.4e})")

            sig = "SIGNIFICATIVO" if corr["spearman_p"] < 0.05 else "não significativo"
            direcao = "positiva" if corr["spearman_r"] > 0 else "negativa"
            print(f"\n  Correlação {direcao} e {sig} (α = 0.05).")
            if corr["spearman_p"] < 0.05:
                if corr["spearman_r"] > 0:
                    print("  → Municípios mais centrais tendem a ter MAIOR taxa de feminicídio.")
                else:
                    print("  → Municípios mais centrais tendem a ter MENOR taxa de feminicídio.")
            else:
                print("  → Sem associação estatisticamente detectável entre BC e taxa.")

        # --- Exportação CSV ---
        exportar_csv(G, bc, caminho=f"../data/results/betweenness_{slug}.csv")

        # --- Plots ---
        if not args.sem_plots:
            plotar_distribuicao_bc(
                res_bc["valores"], nome,
                caminho_saida=f"../data/results/bc_distribuicao_{slug}.png"
            )
            if corr:
                plotar_correlacao_bc_taxa(
                    corr, nome,
                    caminho_saida=f"../data/results/bc_correlacao_taxa_{slug}.png"
                )
            plotar_top_municipios(
                df_top, nome,
                caminho_saida=f"../data/results/bc_top_municipios_{slug}.png"
            )


if __name__ == "__main__":
    main()
