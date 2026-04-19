"""
Grafo de municípios de Minas Gerais baseado em conexões rodoviárias reais.

Estratégia:
  - Rodovias: GEOFABRIK (OpenStreetMap) — Região Sudeste
              sudeste-latest-free.shp.zip → gis_osm_roads_free_1.shp
  - Municípios: IBGE — Malha Municipal 2022
  - Aresta: dois municípios estão conectados se uma rodovia cruza ambos
  - Peso: distância euclidiana entre centroides (km), em projeção UTM

Diferença em relação a main.py (adjacência geográfica):
  - main.py liga municípios que compartilham FRONTEIRA
  - Este arquivo liga municípios que possuem CONEXÃO RODOVIÁRIA REAL

Dependências:
    pip install geopandas networkx matplotlib shapely requests
"""

import io
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

IBGE_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2022/"
    "UFs/MG/MG_Municipios_2022.zip"
)

GEOFABRIK_URL = (
    "https://download.geofabrik.de/south-america/brazil/"
    "sudeste-latest-free.shp.zip"
)

DATA_DIR = Path("data")
IBGE_SHP = DATA_DIR / "MG_Municipios_2022.shp"
ROADS_SHP = DATA_DIR / "gis_osm_roads_free_1.shp"

# Tipos de via relevantes para ligações intermunicipais
# Excluímos residential, service, track, path etc. (vias urbanas/rurais menores)
TIPOS_RELEVANTES = {
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
}


# ---------------------------------------------------------------------------
# 1. Download dos dados
# ---------------------------------------------------------------------------

def baixar_ibge() -> gpd.GeoDataFrame:
    """Baixa (se necessário) e carrega a malha municipal de MG do IBGE."""
    if not IBGE_SHP.exists():
        print("Baixando malha municipal do IBGE (~30 MB)...")
        DATA_DIR.mkdir(exist_ok=True)
        with urllib.request.urlopen(IBGE_URL) as resp:
            dados = resp.read()
        with zipfile.ZipFile(io.BytesIO(dados)) as zf:
            zf.extractall(DATA_DIR)
        print("IBGE: download concluído.")
    else:
        print("IBGE: malha já disponível localmente.")

    gdf = gpd.read_file(IBGE_SHP)
    return gdf.to_crs(epsg=31983)  # SIRGAS 2000 / UTM zone 23S (métrico)


def baixar_rodovias_geofabrik() -> gpd.GeoDataFrame:
    """
    Baixa (se necessário) o shapefile de rodovias do GEOFABRIK e carrega
    apenas a camada de estradas (gis_osm_roads_free_1.shp).

    O arquivo zip tem ~2 GB; o download pode levar alguns minutos.
    """
    if not ROADS_SHP.exists():
        print("Baixando rodovias do GEOFABRIK (~2 GB) — pode demorar alguns minutos...")
        DATA_DIR.mkdir(exist_ok=True)
        with urllib.request.urlopen(GEOFABRIK_URL) as resp:
            dados = resp.read()
        with zipfile.ZipFile(io.BytesIO(dados)) as zf:
            # Extrai apenas os arquivos da camada de rodovias
            membros_roads = [
                m for m in zf.namelist()
                if "gis_osm_roads_free_1" in m
            ]
            zf.extractall(DATA_DIR, members=membros_roads)
        print("GEOFABRIK: download concluído.")
    else:
        print("GEOFABRIK: rodovias já disponíveis localmente.")

    roads = gpd.read_file(ROADS_SHP)
    return roads.to_crs(epsg=31983)


# ---------------------------------------------------------------------------
# 2. Pré-processamento das rodovias
# ---------------------------------------------------------------------------

def filtrar_rodovias_mg(
    roads: gpd.GeoDataFrame,
    gdf_mg: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Filtra as rodovias para:
      1. Apenas tipos relevantes para ligações intermunicipais
      2. Apenas segmentos que intersectam o território de MG
    """
    print("Filtrando rodovias por tipo e recortando para MG...")

    roads_filtradas = roads[roads["fclass"].isin(TIPOS_RELEVANTES)].copy()

    # União de todos os polígonos municipais de MG como máscara de recorte
    mg_contorno = gdf_mg.geometry.union_all()
    roads_mg = roads_filtradas[roads_filtradas.intersects(mg_contorno)].copy()

    print(
        f"  Segmentos totais no Sudeste : {len(roads):>7,}\n"
        f"  Após filtro de tipo         : {len(roads_filtradas):>7,}\n"
        f"  Dentro de MG                : {len(roads_mg):>7,}"
    )
    return roads_mg


# ---------------------------------------------------------------------------
# 3. Construção do grafo
# ---------------------------------------------------------------------------

def construir_grafo(
    gdf: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
) -> nx.Graph:
    """
    Constrói um grafo não-direcionado onde:
      - Vértice  = município
      - Aresta   = existe ao menos um segmento de rodovia que cruza ambos
                   os polígonos municipais simultaneamente
      - Peso     = distância euclidiana entre centroides (km)
      - Atributo 'rodovias' = conjunto de refs/nomes das vias que conectam o par
    """
    print("Construindo grafo rodoviário...")

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

    # Índice espacial dos municípios para acelerar as buscas. 
    # Aqui é calculado apenas um retangulo aproximado do municipio, onde quando as rodovias são consultadas, 
    # conseguimos descartar boa parte dos municipios e termos bons candidatos para rodar o algoritmo intersection, o qual tem um custo computacional relativamente alto. 
    # Sendo assim, conseguimos evitar comparações desnecessárias.

    sindex_mun = gdf.sindex

    # Para cada segmento de rodovia, descobrir quais municípios ele cruza
    total = len(roads)
    for i, (_, road) in enumerate(roads.iterrows()):
        if i % 10_000 == 0:
            print(f"  Processando segmento {i:>7,} / {total:,}...", end="\r")

        # Para cada candidato pelo bounding-box, calcula a interseção geométrica
        # real uma única vez. O resultado é guardado junto com o nome do município
        # para ser reutilizado na ordenação, evitando recalcular intersection().
        # Como a base GEOFABRIK (OpenStreetMap) cria um novo trecho a cada mudança de caracteristica da via, (aslfato, 2 faixas)),
        # (asfalto, 1 faixa). Sempre estamos olhando para um segmento de uma via (apesar de sabermos o nome e onde estamos na via)
        candidatos = list(sindex_mun.intersection(road.geometry.bounds))
        municipios_cruzados = []  # lista de (nome, geometria_de_intersecao)
        for idx_mun in candidatos:
            mun = gdf.iloc[idx_mun]
            intersecao = road.geometry.intersection(mun.geometry)
            if not intersecao.is_empty:
                municipios_cruzados.append((mun["NM_MUN"], intersecao))

        # Um segmento que cruza apenas 1 município não gera aresta
        if len(municipios_cruzados) < 2:
            continue

        # Identificador da rodovia (ref tem prioridade sobre name).
        # Os campos podem conter NaN (float) quando não cadastrados no OSM,
        # por isso usamos pd.notna antes de usar o valor.
        ref_raw = road["ref"] if pd.notna(road["ref"]) else road["name"]
        ref = str(ref_raw) if pd.notna(ref_raw) else "s/ref"

        # Ordena os municípios pela posição ao longo do segmento de rodovia,
        # para criar arestas apenas entre municípios consecutivos (A-B e B-C,
        # não A-C), evitando conexões espúrias de longa distância.
        # Reutiliza a geometria de interseção já calculada acima.
        # Aqui é calculado a distância real ao longo da rodovia entre os municípios.
        ordem = []
        for nome_mun, intersecao in municipios_cruzados:
            ponto_ref = intersecao.representative_point()
            dist_ao_longo = road.geometry.project(ponto_ref)
            ordem.append((dist_ao_longo, nome_mun))


        # Exemplo de como a lista 'ordem' pode ficar após o processamento e o .sort():
        # ordem = [
        #     (0.000, "Betim"),    # Início do segmento de rodovia atravessando Betim
        #     (89.000, "Juatuba"), # Depois, atravessa Juatuba no km 89 da rodovia
        # ]

        ordem.sort()
        municipios_ordenados = [nome for _, nome in ordem]

        # Cria arestas apenas entre municípios consecutivos na ordem da via
        # Aqui é calculado apenas a distância euclidiana entre os centroides dos municípios, não a distância real ao longo da rodovia.
        for mun_a, mun_b in zip(municipios_ordenados[:-1], municipios_ordenados[1:]):
            if G.has_edge(mun_a, mun_b):
                G[mun_a][mun_b]["rodovias"].add(ref)
            else:
                c1 = gdf.loc[gdf["NM_MUN"] == mun_a, "geometry"].values[0].centroid
                c2 = gdf.loc[gdf["NM_MUN"] == mun_b, "geometry"].values[0].centroid
                dist_km = round(c1.distance(c2) / 1000, 2)
                G.add_edge(mun_a, mun_b, weight=dist_km, rodovias={ref})

    print()  # quebra de linha após o \r

    # Converte sets de rodovias para strings ordenadas (mais fácil de exportar).
    # Garante que todos os elementos sejam str, descartando qualquer NaN residual.
    for u, v in G.edges():
        refs_limpos = sorted(str(r) for r in G[u][v]["rodovias"] if pd.notna(r))
        G[u][v]["rodovias"] = ", ".join(refs_limpos)

    print(f"Grafo criado: {G.number_of_nodes()} vértices, {G.number_of_edges()} arestas")
    return G


# ---------------------------------------------------------------------------
# 4. Algoritmos sobre o grafo
# ---------------------------------------------------------------------------

def menor_caminho(G: nx.Graph, origem: str, destino: str) -> list[str]:
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
    except nx.NodeNotFound as e:
        print(f"Município não encontrado: {e}")
        return []


def estatisticas(G: nx.Graph):
    """Exibe métricas básicas do grafo."""
    graus = dict(G.degree())
    mais_conectado = max(graus, key=graus.get)
    isolados = [n for n, g in graus.items() if g == 0]

    print("\n--- Estatísticas do Grafo (rodoviário) ---")
    print(f"  Municípios (vértices)      : {G.number_of_nodes()}")
    print(f"  Conexões rodoviárias (ares): {G.number_of_edges()}")
    print(f"  Grau médio                 : {sum(graus.values()) / len(graus):.2f}")
    print(f"  Município mais conectado   : {mais_conectado} (grau {graus[mais_conectado]})")
    print(f"  Municípios isolados        : {len(isolados)}")
    if isolados:
        print(f"    {isolados[:10]}{'...' if len(isolados) > 10 else ''}")
    print(f"  Grafo conectado?           : {nx.is_connected(G)}")
    if not nx.is_connected(G):
        componentes = list(nx.connected_components(G))
        print(f"  Componentes conexas        : {len(componentes)}")


# ---------------------------------------------------------------------------
# 5. Visualização
# ---------------------------------------------------------------------------

def visualizar_grafo(
    G: nx.Graph,
    gdf: gpd.GeoDataFrame,
    caminho: list[str] | None = None,
    saida: str = "grafo_mg_rodoviario.png",
):
    """
    Plota o mapa de MG com as arestas de conexão rodoviária.
    Destaca o caminho mínimo quando fornecido.
    """
    gdf_plot = gdf.to_crs(epsg=4326)
    gdf_wgs = gdf_plot.set_index("NM_MUN")

    pos = {
        nome: (row.geometry.centroid.x, row.geometry.centroid.y)
        for nome, row in gdf_wgs.iterrows()
        if nome in G.nodes
    }

    fig, ax = plt.subplots(figsize=(14, 12))
    gdf_plot.plot(ax=ax, color="#f0f0f0", edgecolor="#bbb", linewidth=0.3)

    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.25, edge_color="#4a90d9", width=0.5)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=8, node_color="#2b7bba", alpha=0.8)

    if caminho and len(caminho) >= 2:
        edges_caminho = list(zip(caminho[:-1], caminho[1:]))
        nx.draw_networkx_edges(
            G, pos, edgelist=edges_caminho, ax=ax,
            edge_color="red", width=2.5, alpha=0.9,
        )
        nx.draw_networkx_nodes(
            G, pos, nodelist=caminho, ax=ax,
            node_size=40, node_color="red",
        )
        nx.draw_networkx_labels(
            G, pos, labels={n: n for n in [caminho[0], caminho[-1]]},
            ax=ax, font_size=7, font_color="black",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
        )

    ax.set_title(
        "Grafo de Conexões Rodoviárias — Municípios de Minas Gerais\n"
        "(Fonte: OpenStreetMap via GEOFABRIK + IBGE 2022)",
        fontsize=13,
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(saida, dpi=150, bbox_inches="tight")
    print(f"\nMapa salvo em {saida}")
    plt.show()


# ---------------------------------------------------------------------------
# 6. Exportação
# ---------------------------------------------------------------------------

def exportar_grafo(G: nx.Graph, prefixo: str = "grafo_mg_rodoviario"):
    """
    Exporta o grafo nos formatos GraphML e GEXF.

    Atributos exportados por nó : geocodigo, lat, lon (WGS84)
    Atributos exportados por aresta: weight (km), rodovias (string)
    """
    graphml_path = f"{prefixo}.graphml"
    gexf_path = f"{prefixo}.gexf"

    nx.write_graphml(G, graphml_path)
    print(f"Grafo exportado: {graphml_path}")

    nx.write_gexf(G, gexf_path)
    print(f"Grafo exportado: {gexf_path}")


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Carrega municípios de MG (IBGE)
    gdf = baixar_ibge()

    # Carrega rodovias do GEOFABRIK e filtra para MG
    roads_raw = baixar_rodovias_geofabrik()
    roads_mg = filtrar_rodovias_mg(roads_raw, gdf)

    # Constrói o grafo
    G = construir_grafo(gdf, roads_mg)

    # Exporta nos formatos GraphML e GEXF
    exportar_grafo(G)

    # Estatísticas
    estatisticas(G)

    # Menor caminho entre duas cidades
    caminho = menor_caminho(G, "Belo Horizonte", "Paracatu")

    # Visualiza
    visualizar_grafo(G, gdf, caminho)
