import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy import stats

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"

sys.path.insert(0, str(ROOT / "scripts" / "graph-builders"))
from graph_discovery import discover_graph_paths, parse_graph_name
from mesoregion_mapping import MESOREGION_LABELS


def read_graph(path: str | Path) -> nx.Graph:
    path = Path(path)
    if not path.exists():
        print(f"[ERROR] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading graph from: {path}")
    G = nx.read_graphml(path)

    for node, data in G.nodes(data=True):
        value = data.get("taxa_feminicidio_norm")
        if value is not None:
            try:
                G.nodes[node]["taxa_feminicidio_norm"] = float(value)
            except (ValueError, TypeError):
                G.nodes[node]["taxa_feminicidio_norm"] = float("nan")

    return G


def print_femicide_rate_statistics(G: nx.Graph) -> None:
    attributes = [
        float(data.get("taxa_feminicidio_norm"))
        for _, data in G.nodes(data=True)
    ]
    values = np.array(attributes)

    print(f"\n  Total nodes : {G.number_of_nodes()}")
    print(f"  Min | Max   : {float(values.min()):.4f} | {float(values.max()):.4f}")
    print(f"  Mean ± Std  : {float(values.mean()):.4f} ± {float(values.std()):.4f}")


def interpret_assortativity(correlation: float) -> str:
    if correlation > 0.3:
        return "STRONGLY ASSORTATIVE: neighboring municipalities tend to have similar rates"
    if correlation > 0.1:
        return "MODERATELY ASSORTATIVE: slight spatial clustering tendency"
    if correlation > -0.1:
        return "NEARLY NEUTRAL: no clear spatial clustering pattern"
    if correlation > -0.3:
        return "MODERATELY DISASSORTATIVE: neighboring municipalities tend to have different rates"
    return "STRONGLY DISASSORTATIVE: neighboring municipalities have contrasting rates"


def calculate_assortativity(G: nx.Graph) -> dict:
    attribute = "taxa_feminicidio_norm"

    pearson_r_nx = nx.numeric_assortativity_coefficient(G, attribute)

    origin_values = []
    target_values = []
    for origin, target in G.edges():
        origin_values.append(G.nodes[origin][attribute])
        target_values.append(G.nodes[target][attribute])

    origin_values = np.array(origin_values)
    target_values = np.array(target_values)

    pearson_r, pearson_p = stats.pearsonr(origin_values, target_values)
    spearman_r, spearman_p = stats.spearmanr(origin_values, target_values)

    result = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "pearson_r_nx": float(pearson_r_nx),
        "pearson_r_scipy": float(pearson_r),
        "pearson_p_scipy": float(pearson_p),
        "spearman_r_scipy": float(spearman_r),
        "spearman_p_scipy": float(spearman_p),
        "origin_values": origin_values,
        "target_values": target_values,
    }

    print(f"\n  --- Assortativity ({attribute}) ---")
    print(f"  Pearson r (NetworkX) : {result['pearson_r_nx']:.6f}")
    print(
        f"  Pearson r (scipy)    : {result['pearson_r_scipy']:.6f}  "
        f"(p = {result['pearson_p_scipy']:.4e})"
    )
    print(
        f"  Spearman r           : {result['spearman_r_scipy']:.6f}  "
        f"(p = {result['spearman_p_scipy']:.4e})"
    )
    print(f"\n  Interpretation:     {interpret_assortativity(result['pearson_r_nx'])}")

    return result


def build_results_row(graph_name: str, result: dict) -> dict:
    metadata = parse_graph_name(graph_name)
    mesoregion_slug = metadata["mesoregion_slug"]
    mesoregion_label = (
        MESOREGION_LABELS.get(mesoregion_slug, "Minas Gerais (state)")
        if mesoregion_slug != "all"
        else "Minas Gerais (state)"
    )

    return {
        "graph_name": graph_name,
        "scope": metadata["scope"],
        "graph_type": metadata["graph_type"],
        "mesoregion_slug": mesoregion_slug,
        "mesoregion_label": mesoregion_label,
        "nodes": result.get("nodes"),
        "edges": result.get("edges"),
        "pearson_r_nx": result.get("pearson_r_nx"),
        "pearson_r_scipy": result.get("pearson_r_scipy"),
        "pearson_p_scipy": result.get("pearson_p_scipy"),
        "spearman_r_scipy": result.get("spearman_r_scipy"),
        "spearman_p_scipy": result.get("spearman_p_scipy"),
        "interpretation": interpret_assortativity(result.get("pearson_r_nx", 0)),
    }


def save_results(
    results: dict[str, dict],
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    if output_path is None:
        output_path = RESULTS_DIR / "assortativity_results.csv"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [build_results_row(graph_name, result) for graph_name, result in results.items()]
    dataframe = pd.DataFrame(rows)
    dataframe.to_csv(output_path, index=False, float_format="%.6f")
    print(f"\nSaved results to: {output_path}\n")
    return dataframe


def plot_assortativity_comparison(results_df: pd.DataFrame) -> None:
    meso_df = results_df[results_df["scope"] == "mesoregion"].copy()
    if meso_df.empty:
        print("[WARNING] No mesoregion results available for comparison plot.")
        return

    order = [
        MESOREGION_LABELS[slug]
        for slug in MESOREGION_LABELS
        if slug in set(meso_df["mesoregion_slug"])
    ]
    meso_df["mesoregion_label"] = pd.Categorical(
        meso_df["mesoregion_label"],
        categories=order,
        ordered=True,
    )
    meso_df = meso_df.sort_values(["mesoregion_label", "graph_type"])

    graph_types = sorted(meso_df["graph_type"].unique())
    x_positions = np.arange(len(order))
    bar_width = 0.35 if len(graph_types) == 2 else 0.25

    fig, axis = plt.subplots(figsize=(14, 6))
    for index, graph_type in enumerate(graph_types):
        subset = meso_df[meso_df["graph_type"] == graph_type]
        values = [
            subset.loc[subset["mesoregion_label"] == label, "pearson_r_nx"].squeeze()
            if label in subset["mesoregion_label"].values
            else np.nan
            for label in order
        ]
        offset = (index - (len(graph_types) - 1) / 2) * bar_width
        axis.bar(
            x_positions + offset,
            values,
            width=bar_width,
            label=f"{'rodovias' if graph_type.replace('_', ' ') == 'highways' else 'fronteiras físicas'}",
            alpha=0.85,
        )

    state_df = results_df[results_df["scope"] == "state"]
    for _, row in state_df.iterrows():
        axis.axhline(
            row["pearson_r_nx"],
            linestyle="--",
            linewidth=1.2,
            alpha=0.7,
            label=f"Grafo completo de conexões por {'rodovias' if row['graph_type'].replace('_', ' ') == 'highways' else 'fronteiras físicas'}",
        )

    axis.axhline(0, color="black", linewidth=0.8, alpha=0.4)
    axis.set_xticks(x_positions)
    axis.set_xticklabels(order, rotation=45, ha="right")
    axis.set_ylabel("Assortatividade (Coeficiente de Correlação de Pearson)")
    axis.set_title("Assortatividade por Mesorregião e Tipo de Grafo")
    axis.legend(fontsize=8, loc="best")
    axis.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    output_path = RESULTS_DIR / "assortativity_comparison_by_mesoregion.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Comparison plot saved to: {output_path}")


def save_scope_summaries(results_df: pd.DataFrame) -> None:
    state_summary = results_df[results_df["scope"] == "state"].copy()
    meso_summary = results_df[results_df["scope"] == "mesoregion"].copy()

    if not state_summary.empty:
        state_path = RESULTS_DIR / "assortativity_state_summary.csv"
        state_summary.to_csv(state_path, index=False, float_format="%.6f")
        print(f"State summary saved to: {state_path}")

    if not meso_summary.empty:
        meso_path = RESULTS_DIR / "assortativity_mesoregion_summary.csv"
        meso_summary.to_csv(meso_path, index=False, float_format="%.6f")
        print(f"Mesoregion summary saved to: {meso_path}")


def analyze_graph(G: nx.Graph, graph_name: str) -> dict:
    print_femicide_rate_statistics(G)
    return calculate_assortativity(G)


def main() -> None:
    graph_paths = discover_graph_paths()
    results = {}

    for graph_name, graph_path in graph_paths.items():
        print("\n" + "=" * 60)
        print(f"  Graph: {graph_name}")
        print("=" * 60)

        G = read_graph(graph_path)
        results[graph_name] = analyze_graph(G, graph_name)

    if results:
        results_df = save_results(results)
        save_scope_summaries(results_df)
        plot_assortativity_comparison(results_df)


if __name__ == "__main__":
    main()
