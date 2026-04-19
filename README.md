# MC859 — Grafos de Municípios de Minas Gerais

Grafos dos 853 municípios de Minas Gerais construídos com dados públicos do IBGE e OpenStreetMap. Dois modelos são gerados: adjacência geográfica (municípios com fronteira comum) e conectividade rodoviária real (municípios ligados por rodovias). Projeto para a disciplina MC859 — UNICAMP.

## Modelos de Grafo

| Grafo | Arestas | Critério | Script |
|---|---|---|---|
| `grafo_mg_adjacencia` | 2.424 | Fronteira geográfica comum | `main.py` |
| `grafo_mg_rodoviario` | 1.724 | Conexão por rodovia real (OSM) | `main_geofabrik.py` |

**Atributos dos vértices:** nome do município, código IBGE, latitude e longitude (WGS84).  
**Atributos das arestas:** distância euclidiana entre centroides (km). O grafo rodoviário inclui também as rodovias que conectam cada par (`BR-040`, `MG-010`, etc.).

**Formatos de exportação:** GraphML (`.graphml`) e GEXF (`.gexf`), compatíveis com [Gephi](https://gephi.org/) e NetworkX.

## Fontes de Dados

Os dados brutos **não estão incluídos no repositório** (tamanhos proibitivos). Os scripts fazem o download automaticamente na primeira execução.

### 1. IBGE — Malha Municipal 2022

Polígonos geográficos dos 853 municípios de Minas Gerais.

- **Atributos utilizados:** `NM_MUN` (nome), `CD_MUN` (código IBGE de 7 dígitos), `AREA_KM2` (área em km²), `geometry` (polígono do território)
- **Projeção:** SIRGAS 2000 geográfico (EPSG:4674) → reprojetado para UTM zone 23S (EPSG:31983) nos cálculos; WGS84 (EPSG:4326) na exportação
- **Licença:** Dados públicos — Governo Federal do Brasil
- **Download (~30 MB):** [MG_Municipios_2022.zip](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/MG/MG_Municipios_2022.zip)
- **Arquivo local:** `data/MG_Municipios_2022.shp`
- **Uso:** base para os vértices dos dois grafos. Os centroides dos polígonos definem a posição geográfica dos nós e o peso das arestas (distância euclidiana em km).

### 2. GEOFABRIK / OpenStreetMap — Malha Rodoviária Sudeste

Segmentos de rodovias de Minas Gerais extraídos do OpenStreetMap e distribuídos pela Geofabrik. Cobre rodovias federais (BRs), estaduais (MGs) e municipais.

- **Atributos utilizados:** `fclass` (classificação da via), `ref` (ex: BR-040, MG-010), `name`, `geometry` (LineString do traçado)
- **Tipos de via incluídos:** motorway, trunk, primary, secondary, tertiary e suas variantes `_link`
- **Projeção:** reprojetado para UTM zone 23S (EPSG:31983)
- **Licença:** [Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/) — © OpenStreetMap Contributors
- **Download (~2 GB):** [sudeste-latest-free.shp.zip](https://download.geofabrik.de/south-america/brazil/sudeste-latest-free.shp.zip)
- **Arquivo local:** `data/gis_osm_roads_free_1.shp`
- **Uso:** base para as arestas do `grafo_mg_rodoviario`. Dois municípios são conectados quando ao menos um segmento de rodovia cruza ambos os polígonos. Os municípios são ordenados pela posição ao longo do segmento para criar apenas conexões consecutivas (A→B e B→C, nunca A→C direto).

## Instalação

```bash
pip install geopandas networkx matplotlib shapely
```

## Uso

```bash
# Grafo de adjacência geográfica
python main.py

# Grafo de conexões rodoviárias reais
python main_geofabrik.py
```

Ambos os scripts fazem o download dos dados automaticamente se não encontrarem os arquivos na pasta `data/`, constroem o grafo, exibem estatísticas, calculam o menor caminho (Dijkstra) entre Belo Horizonte e Paracatu, e exportam os grafos nos formatos GraphML e GEXF.

## Estrutura do Repositório

```
MC859/
├── main.py                        # Grafo de adjacência geográfica
├── main_geofabrik.py              # Grafo de conectividade rodoviária
├── grafo_mg_adjacencia.graphml
├── grafo_mg_adjacencia.gexf
├── grafo_mg_rodoviario.graphml
├── grafo_mg_rodoviario.gexf
├── grafo_mg.png                   # Visualização do grafo de adjacência
├── grafo_mg_rodoviario.png        # Visualização do grafo rodoviário
└── data/                          # Dados brutos (ignorados pelo git)
    ├── MG_Municipios_2022.shp     # IBGE — baixado automaticamente pelo main.py
    └── gis_osm_roads_free_1.shp   # GEOFABRIK — baixado automaticamente pelo main_geofabrik.py
```
