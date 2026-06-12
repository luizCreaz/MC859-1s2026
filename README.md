# MC859 — Grafos de Municípios de Minas Gerais

Grafos dos 853 municípios de Minas Gerais construídos com dados públicos do IBGE e OpenStreetMap. O projeto modela duas formas de conectividade entre municípios — fronteiras físicas e rodovias reais — e aplica métricas de rede (assortatividade e centralidade de intermediação) sobre a taxa normalizada de feminicídio em 2022. Desenvolvido para a disciplina MC859 — UNICAMP.

## Organização do repositório

O projeto segue uma estrutura em camadas de dados (medallion) e separa construção de grafos, cálculo de taxas e análises de rede:

```
MC859-1s2026/
├── README.md
├── data/
│   ├── bronze/                         # Dados brutos e de referência
│   │   ├── ibge/
│   │   │   ├── malha-municipal/        # Shapefile IBGE (baixado no 1º run)
│   │   │   ├── censo-2022/             # População por município
│   │   │   ├── meso-micro-regioes-mg.pdf
│   │   │   └── mesoregion_municipalities.csv
│   │   ├── geofabrik/
│   │   │   └── malha-rodoviaria/       # Shapefile OSM (baixado no 1º run)
│   │   └── portal-dados-abertos/
│   │       └── mapa-violencia-mulher-mg/ # Casos de feminicídio MG 2022
│   ├── silver/                         # Dados tratados
│   │   └── taxa_feminicidio_mg_2022.csv
│   └── gold/                           # Grafos finais (GraphML + PNG)
│       ├── graph_mg_physical_boundaries.graphml
│       ├── graph_mg_highways.graphml
│       └── mesoregions/                # Subgrafos por mesorregião IBGE
│           ├── graph_mg_physical_boundaries_{mesoregion}.graphml
│           └── graph_mg_highways_{mesoregion}.graphml
├── results/
│   └── report/                         # Tabelas e gráficos do relatório acadêmico
└── scripts/
    ├── calculate_femicide_rate.py
    ├── run_analysis_pipeline.sh        # Pipeline completo de análise
    ├── graph-builders/
    │   ├── build_graph_mg_physical_boundaries.py
    │   ├── build_graph_mg_highways.py
    │   ├── build_mesoregion_subgraphs.py
    │   ├── mesoregion_mapping.py
    │   └── graph_discovery.py
    └── graph-algorithms/
        ├── assortativity/
        │   ├── calculate_assortativity.py
        │   └── results/
        ├── betweeness-centrality/
        │   ├── calculate_betweenness_centrality.py
        │   └── results/
        └── generate_report_tables.py
```

| Camada / pasta | Conteúdo |
|---|---|
| `data/bronze/` | Entradas originais: malhas geográficas, rodovias, censos, violência contra a mulher e tabela de mesorregiões |
| `data/silver/` | Taxa de feminicídio calculada e normalizada por município |
| `data/gold/` | Grafos estaduais e subgrafos por mesorregião, prontos para análise |
| `scripts/graph-builders/` | Download, construção e exportação dos grafos |
| `scripts/graph-algorithms/` | Cálculo de métricas de rede e geração de relatório |
| `results/report/` | Tabelas T1–T5 e gráficos comparativos entre mesorregiões |

## Modelos de grafo

| Grafo | Arquivo | Critério de conexão | Script |
|---|---|---|---|
| Fronteiras físicas | `graph_mg_physical_boundaries` | Municípios com fronteira geográfica em comum | `scripts/graph-builders/build_graph_mg_physical_boundaries.py` |
| Rodovias | `graph_mg_highways` | Municípios ligados por segmento rodoviário real (OSM) | `scripts/graph-builders/build_graph_mg_highways.py` |

**Atributos dos vértices:** nome do município (`id` do nó), código IBGE (`geocodigo`), latitude e longitude (WGS84) e taxa normalizada de feminicídio (`taxa_feminicidio_norm`).

**Atributos das arestas:** distância euclidiana entre centroides em km (`weight`). No grafo rodoviário, inclui também o identificador das vias (`rodovias`, ex.: `BR-040`, `MG-010`).

**Formatos de exportação:** GraphML (`.graphml`) e PNG em `data/gold/`, compatíveis com [Gephi](https://gephi.org/) e NetworkX.

### Lógica de construção — grafo de fronteiras físicas

O script `build_graph_mg_physical_boundaries.py`:

1. Baixa e carrega a malha municipal do IBGE (`data/bronze/ibge/malha-municipal/MG_Municipios_2022.shp`).
2. Cria um vértice para cada um dos 853 municípios, com centroides em WGS84 e a taxa normalizada de feminicídio obtida de `calculate_femicide_rate.py`.
3. Conecta dois municípios com uma aresta quando seus polígonos se **tocam** (`geometry.touches`), ou seja, compartilham fronteira territorial.
4. Define o peso da aresta como a distância euclidiana entre os centroides dos dois polígonos, em quilômetros (projeção UTM EPSG:31983 nos cálculos).

Esse modelo representa a **vizinhança geográfica direta**: municípios são adjacentes se fazem fronteira, independentemente de existir rodovia entre eles.

### Lógica de construção — grafo rodoviário

O script `build_graph_mg_highways.py`:

1. Carrega a malha municipal do IBGE (mesma base de vértices do grafo anterior).
2. Baixa e filtra a malha rodoviária do GEOFABRIK/OpenStreetMap (`data/bronze/geofabrik/malha-rodoviaria/gis_osm_roads_free_1.shp`), mantendo apenas tipos relevantes para ligações intermunicipais (motorway, trunk, primary, secondary, tertiary e variantes `_link`).
3. Recorta os segmentos ao território de Minas Gerais.
4. Para cada segmento de rodovia, identifica quais municípios o segmento **cruza** geometricamente.
5. Ordena os municípios cruzados pela posição ao longo do segmento e cria arestas apenas entre pares **consecutivos** (A–B e B–C, nunca A–C direto), evitando conexões espúrias de longa distância.
6. Define o peso da aresta como a distância euclidiana entre centroides (km) e registra as rodovias que conectam o par.

Esse modelo representa a **conectividade por infraestrutura rodoviária real**, que pode diferir da adjacência geográfica (dois municípios podem ser vizinhos sem rodovia direta, ou conectados por via sem compartilhar fronteira longa).

### Subgrafos por mesorregião

O script `build_mesoregion_subgraphs.py` extrai subgrafos induzidos para cada uma das 12 mesorregiões do IBGE, usando o mapeamento município → mesorregião derivado de `data/bronze/ibge/meso-micro-regioes-mg.pdf`. Os subgrafos são exportados em `data/gold/mesoregions/` e reutilizados nas análises de assortatividade e betweenness centrality.

## Fontes de dados

Arquivos grandes (malha municipal, rodovias) **não** entram no repositório; os scripts baixam na primeira execução.

### IBGE — Malha Municipal 2022

- **Download (~30 MB):** [MG_Municipios_2022.zip](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/MG/MG_Municipios_2022.zip)
- **Arquivo local:** `data/bronze/ibge/malha-municipal/MG_Municipios_2022.shp`

### GEOFABRIK / OpenStreetMap — Malha Rodoviária Sudeste

- **Download (~2 GB):** [sudeste-latest-free.shp.zip](https://download.geofabrik.de/south-america/brazil/sudeste-latest-free.shp.zip)
- **Arquivo local:** `data/bronze/geofabrik/malha-rodoviaria/gis_osm_roads_free_1.shp`
- **Licença:** [Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/) — © OpenStreetMap Contributors

### Taxa normalizada de feminicídio em 2022

O script `scripts/calculate_femicide_rate.py` calcula, para cada município:

1. Taxa por 100.000 habitantes = `100.000 × vítimas / população`, usando:
   - `data/bronze/portal-dados-abertos/mapa-violencia-mulher-mg/casos_feminicidio_mg_2022.csv`
   - `data/bronze/ibge/censo-2022/populacao_mg_2022.csv`
2. Taxa normalizada = taxa do município ÷ maior taxa do estado, resultando em valores no intervalo [0, 1].

A saída é `data/silver/taxa_feminicidio_mg_2022.csv`. Esse valor é incorporado como atributo `taxa_feminicidio_norm` em cada vértice dos grafos.

## Métricas de rede

As análises são executadas sobre os grafos estaduais e sobre os 24 subgrafos mesorregionais (12 mesorregiões × 2 tipos de grafo). Os resultados brutos ficam em `scripts/graph-algorithms/*/results/`; tabelas e gráficos comparativos do relatório ficam em `results/report/`.

### Assortatividade

**Pergunta de pesquisa:** municípios vizinhos na rede tendem a ter taxas de feminicídio semelhantes?

O script `scripts/graph-algorithms/assortativity/calculate_assortativity.py` calcula a **assortatividade de Newman** (coeficiente de Pearson) sobre o atributo `taxa_feminicidio_norm` dos nós:

```
r = correlação de Pearson entre taxa_feminicidio_norm(u) e taxa_feminicidio_norm(v)
    para cada aresta (u, v) do grafo
```

Em termos práticos:

- **r > 0** — assortativo: municípios conectados tendem a ter taxas parecidas (agrupamento espacial na rede).
- **r ≈ 0** — neutro: sem padrão claro de agrupamento.
- **r < 0** — dissassortativo: municípios conectados tendem a ter taxas diferentes.

O cálculo usa `networkx.numeric_assortativity_coefficient` e é validado com correlação de Pearson e Spearman via `scipy.stats` sobre os pares de valores nas arestas. A interpretação qualitativa segue limiares em ±0.1 e ±0.3.

### Betweenness centrality

**Pergunta de pesquisa:** quais municípios funcionam como pontes na rede, concentrando caminhos mais curtos entre outros pares?

O script `scripts/graph-algorithms/betweeness-centrality/calculate_betweenness_centrality.py` calcula a centralidade de intermediação para **todos os nós do grafo inteiro**:

```python
nx.betweenness_centrality(G, k=None, normalized=True, weight=None)
```

- `k=None` — usa todos os nós (sem amostragem).
- `normalized=True` — valores no intervalo [0, 1], divididos pelo máximo teórico.
- `weight=None` — caminhos mais curtos em número de arestas (não usa o peso `weight` das arestas).

Um município com BC alto está em muitos caminhos mínimos entre outros pares: atua como **hub estrutural** na rede (rodoviária ou de fronteiras, conforme o grafo).

### Associação entre betweenness centrality e taxa de feminicídio

Após calcular o BC de cada nó, o script avalia se municípios mais centrais na rede tendem a ter taxas de feminicídio mais altas ou mais baixas. Para cada grafo, forma-se um par `(BCᵢ, taxa_feminicidio_normᵢ)` para cada município `i` com dados válidos e calcula-se:

| Estatística | O que mede |
|---|---|
| Correlação de Pearson | Associação linear entre BC e taxa normalizada |
| Correlação de Spearman | Associação monotônica (mais robusta a outliers) |
| p-valor (α = 0,05) | Significância estatística da associação |

Interpretação (impressa pelo script):

- **Spearman positivo e significativo** — municípios mais centrais tendem a ter **maior** taxa normalizada.
- **Spearman negativo e significativo** — municípios mais centrais tendem a ter **menor** taxa normalizada.
- **Não significativo** — sem evidência estatística de associação entre BC e taxa naquele grafo.

Essa análise é **correlacional, não causal**: BC alto indica posição estrutural na rede, mas não implica que a centralidade cause (ou seja causada por) a taxa de feminicídio. Confundidores como população, urbanização e fluxo migratório podem influenciar ambas as variáveis.

## Instalação

Na raiz do repositório:

```bash
pip install geopandas networkx matplotlib shapely pandas scipy numpy
```

Para o mapeamento de mesorregiões a partir do PDF, é necessário também o utilitário `pdftotext` (pacote `poppler-utils` no Linux).

## Uso

Sempre a partir da raiz do projeto:

```bash
# Taxas por município
python3 scripts/calculate_femicide_rate.py

# Grafos estaduais
python3 scripts/graph-builders/build_graph_mg_physical_boundaries.py
python3 scripts/graph-builders/build_graph_mg_highways.py

# Subgrafos por mesorregião
python3 scripts/graph-builders/build_mesoregion_subgraphs.py

# Pipeline completo de análise (subgrafos + métricas + relatório)
./scripts/run_analysis_pipeline.sh
```

O pipeline executa, em sequência: construção dos subgrafos mesorregionais, assortatividade, betweenness centrality e geração das tabelas/gráficos em `results/report/`.

### Saídas do relatório (`results/report/`)

| Arquivo | Descrição |
|---|---|
| `t1_state_panel.csv` | Painel estadual: assortatividade + correlação BC×taxa |
| `t2_mesoregion_panel.csv` | Painel por mesorregião |
| `t3_heterogeneity_ranking.csv` | Ranking de mesorregiões por \|r\| |
| `t4_graph_concordance.csv` | Concordância entre grafos de fronteira e rodoviário |
| `t5_top_bc_nodes_by_mesoregion.csv` | Municípios com maior BC por mesorregião |
| `heatmap_assortativity.png` | Heatmap assortatividade (mesorregião × tipo de grafo) |
| `heatmap_bc_correlation.png` | Heatmap correlação BC×taxa |
| `scatter_*_state_vs_mesoregion.png` | Comparação estado vs mesorregiões |
| `violin_femicide_rate_by_mesoregion.png` | Distribuição da taxa por mesorregião |
