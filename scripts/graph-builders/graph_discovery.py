from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DIR = ROOT / "data" / "gold"

BASE_GRAPH_FILES = {
    "physical_boundaries": GOLD_DIR / "graph_mg_physical_boundaries.graphml",
    "highways": GOLD_DIR / "graph_mg_highways.graphml",
}


def parse_graph_name(graph_name: str) -> dict[str, str]:
    if "__" in graph_name:
        graph_type, mesoregion_slug = graph_name.split("__", 1)
        return {
            "graph_type": graph_type,
            "mesoregion_slug": mesoregion_slug,
            "scope": "mesoregion",
        }
    return {
        "graph_type": graph_name,
        "mesoregion_slug": "all",
        "scope": "state",
    }


def discover_graph_paths() -> dict[str, Path]:
    graph_paths = dict(BASE_GRAPH_FILES)

    if not GOLD_DIR.exists():
        return graph_paths

    for graphml_path in sorted(GOLD_DIR.glob("graph_mg_*.graphml")):
        stem = graphml_path.stem.removeprefix("graph_mg_")
        if stem in BASE_GRAPH_FILES:
            continue

        for graph_type in BASE_GRAPH_FILES:
            prefix = f"{graph_type}_"
            if stem.startswith(prefix):
                mesoregion_slug = stem.removeprefix(prefix)
                graph_name = f"{graph_type}__{mesoregion_slug}"
                graph_paths[graph_name] = graphml_path
                break

    return graph_paths
