"""
Grafo de municípios de Minas Gerais a partir da malha geográfica do IBGE.

Dependências:
    pip install geopandas networkx matplotlib shapely requests

Fonte dos dados:
    IBGE - Malha Municipal 2022
    https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/
            malhas_municipais/municipio_2022/Estados/MG/MG_Municipios_2022.zip
"""

import zipfile
import io
import urllib.request
from pathlib import Path

import geopandas as gpd
import networkx as nx
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# 1. Download e leitura da malha municipal do IBGE
# ---------------------------------------------------------------------------

IBGE_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2022/"
    "UFs/MG/MG_Municipios_2022.zip"
)
DATA_DIR = Path("data")
SHAPEFILE_PATH = DATA_DIR / "MG_Municipios_2022.shp"


def baixar_malha_ibge() -> gpd.GeoDataFrame:
    """Baixa (se necessário) e carrega a malha municipal de MG do IBGE."""
    if not SHAPEFILE_PATH.exists():
        print("Baixando malha municipal do IBGE (~30 MB)...")
        DATA_DIR.mkdir(exist_ok=True)
        with urllib.request.urlopen(IBGE_URL) as response:
            zip_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(DATA_DIR)
        print("Download concluído.")
    else:
        print("Malha já disponível localmente.")

    gdf = gpd.read_file(SHAPEFILE_PATH)
    # Garante CRS métrico para cálculos de distância em km
    gdf = gdf.to_crs(epsg=31983)  # SIRGAS 2000 / UTM zone 23S
    return gdf


# ---------------------------------------------------------------------------
# 2. Construção do grafo
# ---------------------------------------------------------------------------

def construir_grafo(gdf: gpd.GeoDataFrame) -> nx.Graph:
    """
    Constrói um grafo não-direcionado onde:
      - Vértice  = município (identificado pelo nome)
      - Aresta   = municípios com fronteira em comum (geometrias que se tocam)
      - Peso     = distância em km entre os centroides dos dois municípios
    """
    print("Construindo grafo de adjacência...")

    # Índice espacial para acelerar a busca de vizinhos
    sindex = gdf.sindex

    G = nx.Graph()

    # Reprojecta para WGS84 para que lat/lon nos nós sejam graus decimais,
    # compatíveis com GraphML/GEXF e ferramentas como Gephi.
    gdf_wgs = gdf.to_crs(epsg=4326)

    # Adiciona todos os vértices com atributos
    for _, row in gdf_wgs.iterrows():
        centroide = row.geometry.centroid
        G.add_node(
            row["NM_MUN"],
            geocodigo=row["CD_MUN"],
            lat=round(centroide.y, 6),
            lon=round(centroide.x, 6),
        )

    # Adiciona arestas entre municípios vizinhos
    for idx, row in gdf.iterrows():
        # Candidatos pelo bounding-box (rápido)
        candidatos = list(sindex.intersection(row.geometry.bounds))
        for idx2 in candidatos:
            if idx2 <= idx:          # evita duplicatas e auto-laços
                continue
            row2 = gdf.iloc[idx2]
            if row.geometry.touches(row2.geometry):
                c1 = row.geometry.centroid
                c2 = row2.geometry.centroid
                distancia_km = c1.distance(c2) / 1000  # metros → km
                G.add_edge(
                    row["NM_MUN"],
                    row2["NM_MUN"],
                    weight=round(distancia_km, 2),
                )

    print(f"Grafo criado: {G.number_of_nodes()} vértices, {G.number_of_edges()} arestas")
    return G


# ---------------------------------------------------------------------------
# 3. Algoritmos sobre o grafo
# ---------------------------------------------------------------------------

def menor_caminho(G: nx.Graph, origem: str, destino: str):
    """Dijkstra — caminho com menor distância entre centroides."""
    try:
        caminho = nx.dijkstra_path(G, origem, destino, weight="weight")
        distancia = nx.dijkstra_path_length(G, origem, destino, weight="weight")
        print(f"\nMenor caminho ({origem} → {destino}):")
        print("  " + " → ".join(caminho))
        print(f"  Distância total (centroides): {distancia:.1f} km")
        return caminho
    except nx.NetworkXNoPath:
        print(f"Sem caminho entre {origem} e {destino}.")
        return []


def estatisticas(G: nx.Graph):
    """Exibe métricas básicas do grafo."""
    graus = dict(G.degree())
    mais_conectado = max(graus, key=graus.get)
    print("\n--- Estatísticas do Grafo ---")
    print(f"  Municípios (vértices)  : {G.number_of_nodes()}")
    print(f"  Fronteiras (arestas)   : {G.number_of_edges()}")
    print(f"  Grau médio             : {sum(graus.values()) / len(graus):.2f}")
    print(f"  Município mais central : {mais_conectado} (grau {graus[mais_conectado]})")
    print(f"  Grafo conectado?       : {nx.is_connected(G)}")


# ---------------------------------------------------------------------------
# 4. Visualização
# ---------------------------------------------------------------------------

def visualizar_grafo(G: nx.Graph, gdf: gpd.GeoDataFrame, caminho: list[str] = None):
    """
    Plota o mapa de MG com as arestas de adjacência.
    Destaca o caminho mínimo quando fornecido.
    """
    # Reprojecta para graus geográficos (WGS84) para plotagem
    gdf_plot = gdf.to_crs(epsg=4326)

    fig, ax = plt.subplots(figsize=(14, 12))
    gdf_plot.plot(ax=ax, color="#f0f0f0", edgecolor="#999", linewidth=0.3)

    # Posições dos nós = centroides em WGS84
    # Reprojecta de uma vez todo o GDF para evitar loop de conversões
    gdf_wgs = gdf.to_crs(epsg=4326).set_index("NM_MUN")
    pos = {
        nome: (row.geometry.centroid.x, row.geometry.centroid.y)
        for nome, row in gdf_wgs.iterrows()
        if nome in G.nodes
    }

    # Arestas normais
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3, edge_color="#aaaaaa", width=0.5)

    # Nós
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=8, node_color="#2b7bba", alpha=0.8)

    # Destaca caminho mínimo
    if caminho and len(caminho) >= 2:
        edges_caminho = list(zip(caminho[:-1], caminho[1:]))
        nx.draw_networkx_edges(
            G, pos, edgelist=edges_caminho, ax=ax,
            edge_color="red", width=2.5, alpha=0.9
        )
        nx.draw_networkx_nodes(
            G, pos, nodelist=caminho, ax=ax,
            node_size=40, node_color="red"
        )
        # Rótulos apenas da origem e destino
        nx.draw_networkx_labels(
            G, pos, labels={n: n for n in [caminho[0], caminho[-1]]},
            ax=ax, font_size=7, font_color="black",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7)
        )

    ax.set_title("Grafo de Adjacência — Municípios de Minas Gerais (IBGE 2022)", fontsize=14)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig("grafo_mg.png", dpi=150, bbox_inches="tight")
    print("\nMapa salvo em grafo_mg.png")
    plt.show()


# ---------------------------------------------------------------------------
# 5. Exportação
# ---------------------------------------------------------------------------

def exportar_grafo(G: nx.Graph, prefixo: str = "grafo_mg_adjacencia"):
    """
    Exporta o grafo nos formatos GraphML e GEXF.

    Atributos exportados por nó  : geocodigo, lat, lon (WGS84)
    Atributos exportados por aresta: weight (km)
    """
    graphml_path = f"{prefixo}.graphml"
    gexf_path = f"{prefixo}.gexf"

    nx.write_graphml(G, graphml_path)
    print(f"Grafo exportado: {graphml_path}")

    nx.write_gexf(G, gexf_path)
    print(f"Grafo exportado: {gexf_path}")


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Carrega a malha geográfica
    gdf = baixar_malha_ibge()

    # Constrói o grafo
    G = construir_grafo(gdf)

    # Exporta nos formatos GraphML e GEXF
    exportar_grafo(G)

    # Exibe estatísticas
    estatisticas(G)

    # Exemplo: menor caminho entre duas cidades
    caminho = menor_caminho(G, "Belo Horizonte", "Paracatu")

    # Visualiza
    visualizar_grafo(G, gdf, caminho)
