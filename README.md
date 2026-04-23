# MC859 — Grafos de Municípios de Minas Gerais

Grafos dos 853 municípios de Minas Gerais construídos com dados públicos do IBGE e OpenStreetMap. Dois modelos são gerados: adjacência geográfica (municípios com fronteira comum) e conectividade rodoviária real (municípios ligados por rodovias). Projeto para a disciplina MC859 — UNICAMP.

## Modelos de Grafo

| Grafo | Critério | Script |
|---|---|---|
| `grafo_mg_adjacencia` | Fronteira geográfica comum | `scripts/build_graph_ibge.py` |
| `grafo_mg_rodoviario` | Conexão por rodovia real (OSM) | `scripts/build_graph_geofabrik.py` |

**Atributos dos vértices:** nome do município, código IBGE, latitude e longitude (WGS84) e taxa normalizada de feminicídio em 2022.
**Atributos das arestas:** distância euclidiana entre centroides (km). O grafo rodoviário inclui também as rodovias que conectam cada par (`BR-040`, `MG-010`, etc.).

**Formatos de exportação:** GraphML (`.graphml`) e GEXF (`.gexf`) em `data/graphs/`, compatíveis com [Gephi](https://gephi.org/) e NetworkX. Visualizações PNG com o mesmo prefixo de nome estão na mesma pasta.

## Fontes de Dados

Arquivos grandes (malha, rodovias) **não** entram no repositório; os scripts baixam na primeira execução. Os CSVs de feminicídio e população ficam em `data/raw/` (versionáveis, se desejado).

### 1. IBGE — Malha Municipal 2022

Polígonos geográficos dos 853 municípios de Minas Gerais.

- **Atributos utilizados:** `NM_MUN` (nome), `CD_MUN` (código IBGE de 7 dígitos), `AREA_KM2` (área em km²), `geometry` (polígono do território)
- **Projeção:** SIRGAS 2000 geográfico (EPSG:4674) → reprojetado para UTM zone 23S (EPSG:31983) nos cálculos; WGS84 (EPSG:4326) na exportação
- **Licença:** Dados públicos — Governo Federal do Brasil
- **Download (~30 MB):** [MG_Municipios_2022.zip](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/MG/MG_Municipios_2022.zip)
- **Arquivo local após download:** `data/raw/MG_Municipios_2022.shp`
- **Uso:** base para os vértices dos dois grafos. Os centroides dos polígonos definem a posição geográfica dos nós e o peso das arestas (distância euclidiana em km).

### 2. GEOFABRIK / OpenStreetMap — Malha Rodoviária Sudeste

Segmentos de rodovias de Minas Gerais extraídos do OpenStreetMap e distribuídos pela Geofabrik. Cobre rodovias federais (BRs), estaduais (MGs) e municipais.

- **Atributos utilizados:** `fclass` (classificação da via), `ref` (ex: BR-040, MG-010), `name`, `geometry` (LineString do traçado)
- **Tipos de via incluídos:** motorway, trunk, primary, secondary, tertiary e suas variantes `_link`
- **Projeção:** reprojetado para UTM zone 23S (EPSG:31983)
- **Licença:** [Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/) — © OpenStreetMap Contributors
- **Download (~2 GB):** [sudeste-latest-free.shp.zip](https://download.geofabrik.de/south-america/brazil/sudeste-latest-free.shp.zip)
- **Arquivo local após download:** `data/raw/gis_osm_roads_free_1.shp`
- **Uso:** base para as arestas do grafo rodoviário. Dois municípios são conectados quando ao menos um segmento de rodovia cruza ambos os polígonos. Os municípios são ordenados pela posição ao longo do segmento para criar apenas conexões consecutivas (A→B e B→C, nunca A→C direto).

## Dados Agregados 

### Taxa normalizada de feminicídio em 2022

O script `scripts/calculate_femicide_rate.py` calcula a taxa normalizada de feminicídio em 2022 para cada um dos municípios mineiros.

Inicialmente, é calculada a taxa de feminicídio por 100.000 habitantes em cada município, considerando:
- registros de tentativas e consumações de feminicídio no estado de Minas Gerais do [Portal de Dados Abertos do GOV BR](https://dados.gov.br/dados/conjuntos-dados/violencia-contra-mulher) (`data/raw/feminicidio_mg_2022.csv`)
- [Censo Demográfico de 2022 do IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html?edicao=35938&t=resultados) (`data/raw/populacao_mg_2022.csv`)

Depois, divide-se cada uma delas pela maior taxa calculada, de modo a obtermos taxas normalizadas no intervalo [0, 1]. Por fim, salvamos no arquivo `data/processed/taxa_feminicidio_mg_2022.csv`:
- código do município;
- número absoluto de vítimas de tentativas e consumações de feminicídio em 2022;
- população em 2022;
- taxa de feminicídio por 100.000 habitantes em 2022;
- taxa normalizada de feminicídio em 2022.



## Instalação

Na **raiz do repositório**:

```bash
pip install geopandas networkx matplotlib shapely
```

## Uso

Sempre a partir da raiz do projeto (para que os caminhos `data/...` funcionem):

```bash
# Apenas taxas por município (gera data/processed/taxa_feminicidio_mg_2022.csv)
python scripts/calculate_femicide_rate.py

# Grafo de adjacência geográfica (recalcula taxas, exporta em data/graphs/)
python scripts/build_graph_ibge.py

# Grafo de conexões rodoviárias (recalcula taxas, exporta em data/graphs/; exige download grande)
python scripts/build_graph_geofabrik.py
```

Os scripts de grafo, ao rodar, regeneram o CSV de taxas, constroem o grafo, mostram estatísticas, calculam o menor caminho (Dijkstra) entre Belo Horizonte e Paracatu e exportam **GraphML**, **GEXF** e **PNG** em `data/graphs/`. O script rodoviário pode levar muito tempo no primeiro uso por causa do download e do processamento das vias.

## Estrutura do Repositório

```
MC859-1s2026/
├── README.md
├── scripts/
│   ├── build_graph_ibge.py          # Adjacência geográfica (IBGE)
│   ├── build_graph_geofabrik.py     # Conexões por rodovias (GEOFABRIK + OSM)
│   └── calculate_femicide_rate.py  # Taxas 2022 e atributo nos nós
└── data/
    ├── raw/                         # Entradas e caches de download
    │   ├── feminicidio_mg_2022.csv
    │   ├── populacao_mg_2022.csv
    │   ├── MG_Municipios_2022.shp   # IBGE — baixado no primeiro run
    │   └── gis_osm_roads_free_1.shp  # GEOFABRIK — baixado no run rodoviário
    ├── processed/
    │   └── taxa_feminicidio_mg_2022.csv
    └── graphs/
        ├── grafo_mg_adjacencia.graphml
        ├── grafo_mg_adjacencia.gexf
        ├── grafo_mg_adjacencia.png
        ├── grafo_mg_rodoviario.graphml
        ├── grafo_mg_rodoviario.gexf
        └── grafo_mg_rodoviario.png
```
