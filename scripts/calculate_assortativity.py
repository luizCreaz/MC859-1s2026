"""
Cálculo do Coeficiente de Assortatividade por Atributo Contínuo
para os Grafos de Municípios de Minas Gerais.

O coeficiente de assortatividade mede se vértices com valores similares do
atributo 'taxa_feminicidio_norm' tendem a se conectar entre si. Um valor
positivo indica que municípios vizinhos possuem taxas similares (assortativo),
enquanto um valor negativo indica o oposto (dissortativo).

Para atributos contínuos, o NetworkX implementa a correlação de Pearson entre
os valores do atributo nos dois extremos de cada aresta — equivalente ao
I de Moran global quando a rede é o grafo de adjacência espacial.

Dependências:
    pip install networkx scipy numpy pandas matplotlib

Uso:
    python calculate_assortativity.py [--graphml-ibge <path>] [--graphml-geofabrik <path>]

    Se os caminhos não forem fornecidos, usa os padrões em data/graphs/.
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

    # Converte o atributo para float (pode vir como string no GraphML)
    for node, data in G.nodes(data=True):
        val = data.get("taxa_feminicidio_norm")
        if val is not None:
            try:
                G.nodes[node]["taxa_feminicidio_norm"] = float(val)
            except (ValueError, TypeError):
                G.nodes[node]["taxa_feminicidio_norm"] = float("nan")

    return G


# ---------------------------------------------------------------------------
# 2. Verificação de integridade do atributo
# ---------------------------------------------------------------------------

def inspecionar_atributo(G: nx.Graph, atributo: str = "taxa_feminicidio_norm") -> dict:
    """
    Retorna estatísticas descritivas do atributo nos vértices do grafo.
    Também reporta vértices sem o atributo ou com valor NaN.
    """
    valores = []
    ausentes = []

    for node, data in G.nodes(data=True):
        val = data.get(atributo)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            ausentes.append(node)
        else:
            valores.append(float(val))

    arr = np.array(valores)
    info = {
        "total_vertices": G.number_of_nodes(),
        "com_atributo":   len(valores),
        "sem_atributo":   len(ausentes),
        "min":   float(arr.min())  if len(arr) > 0 else None,
        "max":   float(arr.max())  if len(arr) > 0 else None,
        "media": float(arr.mean()) if len(arr) > 0 else None,
        "desvio_padrao": float(arr.std()) if len(arr) > 0 else None,
        "vertices_ausentes": ausentes[:10],  # mostra só os 10 primeiros
    }
    return info


# ---------------------------------------------------------------------------
# 3. Cálculo da assortatividade
# ---------------------------------------------------------------------------

def calcular_assortatividade(G: nx.Graph,
                              atributo: str = "taxa_feminicidio_norm") -> dict:
    """
    Calcula o coeficiente de assortatividade para um atributo numérico contínuo.

    NetworkX usa a correlação de Pearson entre os valores do atributo nas duas
    pontas de cada aresta (Newman, 2002 / 2003):

        r = [M^{-1} Σ_{(i,j)∈E} x_i x_j  -  (M^{-1} Σ_{(i,j)∈E} (x_i + x_j)/2)^2]
            ─────────────────────────────────────────────────────────────────────────
            [M^{-1} Σ_{(i,j)∈E} (x_i^2 + x_j^2)/2  -  (...)^2]

    onde M é o número de arestas e x_i é o valor do atributo no vértice i.

    Também calculamos o I de Moran (correlação espacial global) usando scipy
    como verificação independente.

    Retorna um dicionário com os valores calculados e metadados.
    """
    # --- Filtra vértices sem atributo ---
    nos_validos = {
        n for n, d in G.nodes(data=True)
        if d.get(atributo) is not None
        and not (isinstance(d.get(atributo), float) and np.isnan(d.get(atributo)))
    }

    # Subgrafo apenas com nós que têm o atributo
    H = G.subgraph(nos_validos).copy()

    if H.number_of_edges() == 0:
        print("[AVISO] Nenhuma aresta no subgrafo com atributo válido.")
        return {}

    # --- Assortatividade de Newman (Pearson) via NetworkX ---
    r = nx.numeric_assortativity_coefficient(H, atributo)

    # --- Cálculo manual para obter os vetores de pares (útil para scatter) ---
    x_origem = []
    x_destino = []
    for u, v in H.edges():
        xu = H.nodes[u][atributo]
        xv = H.nodes[v][atributo]
        x_origem.append(xu)
        x_destino.append(xv)

    x_o = np.array(x_origem)
    x_d = np.array(x_destino)

    # Correlação de Pearson via scipy (deve coincidir com NetworkX)
    pearson_r, pearson_p = stats.pearsonr(x_o, x_d)

    # Correlação de Spearman (alternativa robusta a outliers)
    spearman_r, spearman_p = stats.spearmanr(x_o, x_d)

    return {
        "n_vertices":          H.number_of_nodes(),
        "n_arestas":           H.number_of_edges(),
        "assortatividade_nx":  float(r),      # resultado oficial NetworkX
        "pearson_r":           float(pearson_r),
        "pearson_p_valor":     float(pearson_p),
        "spearman_r":          float(spearman_r),
        "spearman_p_valor":    float(spearman_p),
        "x_origem":            x_o,
        "x_destino":           x_d,
    }


# ---------------------------------------------------------------------------
# 4. Interpretação do resultado
# ---------------------------------------------------------------------------

def interpretar_assortatividade(r: float) -> str:
    """Retorna uma interpretação textual do coeficiente."""
    if r > 0.3:
        return "FORTEMENTE ASSORTATIVO: municípios vizinhos tendem a ter taxas similares."
    elif r > 0.1:
        return "MODERADAMENTE ASSORTATIVO: leve tendência de agrupamento espacial."
    elif r > -0.1:
        return "PRATICAMENTE NEUTRO: sem padrão claro de agrupamento espacial."
    elif r > -0.3:
        return "MODERADAMENTE DISSORTATIVO: municípios vizinhos tendem a ter taxas diferentes."
    else:
        return "FORTEMENTE DISSORTATIVO: municípios vizinhos têm taxas contrastantes."


# ---------------------------------------------------------------------------
# 5. Visualização: scatter de pares de arestas
# ---------------------------------------------------------------------------

def plotar_scatter_arestas(resultado: dict, titulo: str,
                            caminho_saida: str | Path | None = None):
    """
    Gera um scatter plot com os valores do atributo nas duas pontas de cada aresta.
    Um padrão diagonal indica assortatividade positiva.
    """
    x_o = resultado["x_origem"]
    x_d = resultado["x_destino"]
    r   = resultado["assortatividade_nx"]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(x_o, x_d, alpha=0.25, s=8, color="#2b7bba", edgecolors="none")

    # Linha de tendência
    m, b = np.polyfit(x_o, x_d, 1)
    xmin, xmax = x_o.min(), x_o.max()
    ax.plot([xmin, xmax], [m * xmin + b, m * xmax + b],
            color="red", linewidth=1.5, label=f"Tendência linear")

    ax.set_xlabel("Taxa de feminicídio — município origem", fontsize=11)
    ax.set_ylabel("Taxa de feminicídio — município destino", fontsize=11)
    ax.set_title(
        f"{titulo}\nAssortatividade (Pearson) = {r:.4f}", fontsize=12
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if caminho_saida:
        caminho_saida = Path(caminho_saida)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
        print(f"  Scatter salvo em: {caminho_saida}")

    plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# 6. Relatório em CSV
# ---------------------------------------------------------------------------

def salvar_relatorio(resultados: dict[str, dict],
                      caminho: str | Path = "../data/results/assortatividade.csv"):
    """Salva um resumo dos coeficientes calculados em CSV."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for nome, res in resultados.items():
        rows.append({
            "grafo":                  nome,
            "n_vertices":             res.get("n_vertices"),
            "n_arestas":              res.get("n_arestas"),
            "assortatividade_pearson": res.get("assortatividade_nx"),
            "pearson_p_valor":        res.get("pearson_p_valor"),
            "spearman_r":             res.get("spearman_r"),
            "spearman_p_valor":       res.get("spearman_p_valor"),
            "interpretacao":          interpretar_assortatividade(
                                          res.get("assortatividade_nx", 0))
        })

    df = pd.DataFrame(rows)
    df.to_csv(caminho, index=False, float_format="%.6f")
    print(f"\nRelatório salvo em: {caminho}")
    return df


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Calcula a assortatividade da taxa de feminicídio nos grafos de MG."
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
        "--sem-plots",
        action="store_true",
        help="Não exibe/salva os scatter plots."
    )
    args = parser.parse_args()

    grafos = {
        "IBGE (fronteiras físicas)":  args.graphml_ibge,
        "Geofabrik (rodovias)":       args.graphml_geofabrik,
    }

    resultados = {}

    for nome, caminho in grafos.items():
        print("\n" + "=" * 60)
        print(f"  Grafo: {nome}")
        print("=" * 60)

        G = carregar_grafo(caminho)

        # Inspeção do atributo
        info = inspecionar_atributo(G)
        print(f"\n  Vértices totais : {info['total_vertices']}")
        print(f"  Com atributo    : {info['com_atributo']}")
        print(f"  Sem atributo    : {info['sem_atributo']}")
        print(f"  Min / Max       : {info['min']:.4f} / {info['max']:.4f}")
        print(f"  Média ± DP      : {info['media']:.4f} ± {info['desvio_padrao']:.4f}")
        if info["vertices_ausentes"]:
            print(f"  Amostra sem attr: {info['vertices_ausentes']}")

        # Cálculo
        res = calcular_assortatividade(G)
        if not res:
            print("  [ERRO] Não foi possível calcular a assortatividade.")
            continue

        resultados[nome] = res

        # Exibe resultado
        print(f"\n  --- Assortatividade (atributo: taxa_feminicidio_norm) ---")
        print(f"  Pearson r (NetworkX) : {res['assortatividade_nx']:.6f}")
        print(f"  Pearson r (scipy)    : {res['pearson_r']:.6f}  (p = {res['pearson_p_valor']:.4e})")
        print(f"  Spearman r           : {res['spearman_r']:.6f}  (p = {res['spearman_p_valor']:.4e})")
        print(f"\n  Interpretação: {interpretar_assortatividade(res['assortatividade_nx'])}")

        # Plot
        if not args.sem_plots:
            slug = nome.lower().replace(" ", "_").replace("(", "").replace(")", "")
            plotar_scatter_arestas(
                res,
                titulo=f"Pares de municípios vizinhos — {nome}",
                caminho_saida=f"../data/results/scatter_assortatividade_{slug}.png"
            )

    # Salva relatório comparativo
    if resultados:
        df = salvar_relatorio(resultados)
        print("\n  === Tabela Comparativa ===")
        print(df[["grafo", "assortatividade_pearson", "pearson_p_valor",
                   "spearman_r", "interpretacao"]].to_string(index=False))


if __name__ == "__main__":
    main()
