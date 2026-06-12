"""
Export mesoregion subgraphs from the state-level MG graphs.

Reads:
  - data/gold/graph_mg_physical_boundaries.graphml
  - data/gold/graph_mg_highways.graphml
  - data/bronze/ibge/meso-micro-regioes-mg.pdf

Writes:
  - data/gold/mesoregions/graph_mg_{graph_type}_{mesoregion_slug}.graphml
  - data/gold/mesoregions/graph_mg_{graph_type}_{mesoregion_slug}.png
  - data/bronze/ibge/mesoregion_municipalities.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_discovery import BASE_GRAPH_FILES, GOLD_DIR, MESOREGION_DIR
from mesoregion_mapping import (
    MESOREGION_LABELS,
    get_mesoregion_groups,
    save_mapping_csv,
)

GRAPH_TYPES = {
    "physical_boundaries": {
        "title": "Physical Boundaries",
        "edge_color": "#aaaaaa",
    },
    "highways": {
        "title": "Highways",
        "edge_color": "#4a90d9",
    },
}


def read_graph(path: Path) -> nx.Graph:
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")
    return nx.read_graphml(path)


def build_subgraph(G: nx.Graph, node_names: list[str], mesoregion_slug: str) -> nx.Graph:
    subgraph = G.subgraph(node_names).copy()
    for node in subgraph.nodes:
        subgraph.nodes[node]["mesoregion_slug"] = mesoregion_slug
        subgraph.nodes[node]["mesoregion_label"] = MESOREGION_LABELS[mesoregion_slug]
    return subgraph


def plot_subgraph(
    G: nx.Graph,
    graph_type: str,
    mesoregion_slug: str,
    output_path: Path,
) -> None:
    positions = {}
    for node, data in G.nodes(data=True):
        lat = data.get("lat")
        lon = data.get("lon")
        if lat is not None and lon is not None:
            positions[node] = (float(lon), float(lat))

    if not positions:
        print(f"[WARNING] No coordinates for plot: {output_path.name}")
        return

    config = GRAPH_TYPES[graph_type]
    fig, axis = plt.subplots(figsize=(10, 8))

    nx.draw_networkx_edges(
        G,
        positions,
        ax=axis,
        alpha=0.35,
        edge_color=config["edge_color"],
        width=0.6,
    )
    nx.draw_networkx_nodes(
        G,
        positions,
        ax=axis,
        node_size=18,
        node_color="#2b7bba",
        alpha=0.85,
    )

    axis.set_title(
        f"{config['title']} — {MESOREGION_LABELS[mesoregion_slug]}\n"
        f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
        fontsize=12,
    )
    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")
    axis.grid(True, alpha=0.2)
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  PNG saved to: {output_path}")


def export_subgraph(
    G: nx.Graph,
    graph_type: str,
    mesoregion_slug: str,
) -> None:
    output_stem = f"graph_mg_{graph_type}_{mesoregion_slug}"
    graphml_path = MESOREGION_DIR / f"{output_stem}.graphml"
    png_path = MESOREGION_DIR / f"{output_stem}.png"

    MESOREGION_DIR.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, graphml_path)
    print(f"  GraphML saved to: {graphml_path}")

    plot_subgraph(G, graph_type, mesoregion_slug, png_path)


def export_mesoregion_subgraphs_for_graph(
    graph_type: str,
    graph_path: Path,
    mesoregion_groups: dict[str, list[str]],
) -> None:
    print(f"\nProcessing base graph: {graph_type}")
    G = read_graph(graph_path)

    for mesoregion_slug, node_names in mesoregion_groups.items():
        subgraph_nodes = [node for node in node_names if node in G]
        if not subgraph_nodes:
            print(f"  [WARNING] No nodes for mesoregion: {mesoregion_slug}")
            continue

        subgraph = build_subgraph(G, subgraph_nodes, mesoregion_slug)
        print(
            f"  Mesoregion {mesoregion_slug}: "
            f"{subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges"
        )
        export_subgraph(subgraph, graph_type, mesoregion_slug)


def main() -> None:
    reference_graph = read_graph(BASE_GRAPH_FILES["physical_boundaries"])
    node_names = list(reference_graph.nodes)
    mesoregion_groups = get_mesoregion_groups(node_names)

    mapping_path = save_mapping_csv(node_names)
    print(f"Municipality mapping saved to: {mapping_path}")

    for graph_type, graph_path in BASE_GRAPH_FILES.items():
        export_mesoregion_subgraphs_for_graph(graph_type, graph_path, mesoregion_groups)

    print(f"\nMesoregion subgraphs exported under: {MESOREGION_DIR}")


if __name__ == "__main__":
    main()
