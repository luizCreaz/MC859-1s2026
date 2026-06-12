import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from scipy import stats

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"
TOP_NODES_COUNT = 10

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
        for key in ("taxa_feminicidio_norm", "lat", "lon"):
            value = data.get(key)
            if value is not None:
                try:
                    G.nodes[node][key] = float(value)
                except (ValueError, TypeError):
                    pass

    return G


def calculate_betweenness(G: nx.Graph) -> dict:
    betweenness = nx.betweenness_centrality(
        G,
        k=None,
        normalized=True,
        weight=None,
        seed=45,
    )
    values = np.array(list(betweenness.values()))

    result = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "betweenness_centrality": betweenness,
        "values": values,
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std()),
        "percentile_90": float(np.percentile(values, 90)),
        "percentile_95": float(np.percentile(values, 95)),
        "percentile_99": float(np.percentile(values, 99)),
    }

    print("\n  --- Betweenness Centrality statistics ---")
    print(f"  Nodes    : {G.number_of_nodes()}")
    print(f"  Edges    : {G.number_of_edges()}")
    print(f"  BC min   : {result['min']:.8f}")
    print(f"  BC max   : {result['max']:.8f}")
    print(f"  BC mean  : {result['mean']:.8f}")
    print(f"  BC median: {result['median']:.8f}")
    print(f"  BC std   : {result['std']:.8f}")
    print(
        f"  Percentile 90/95/99: {result['percentile_90']:.6f} / "
        f"{result['percentile_95']:.6f} / {result['percentile_99']:.6f}"
    )

    return result


def correlate_bc_with_femicide_rate(G: nx.Graph, betweenness: dict) -> dict:
    attribute = "taxa_feminicidio_norm"
    pairs = []

    for node, data in G.nodes(data=True):
        femicide_rate = data.get(attribute)
        bc_value = betweenness.get(node)
        if femicide_rate is None or bc_value is None:
            continue
        if isinstance(femicide_rate, float) and np.isnan(femicide_rate):
            continue
        pairs.append((float(femicide_rate), float(bc_value)))

    if len(pairs) < 10:
        print("[WARNING] Too few valid pairs for correlation.")
        return {}

    femicide_rates = np.array([pair[0] for pair in pairs])
    bc_values = np.array([pair[1] for pair in pairs])

    pearson_r, pearson_p = stats.pearsonr(bc_values, femicide_rates)
    spearman_r, spearman_p = stats.spearmanr(bc_values, femicide_rates)

    result = {
        "n_pairs": len(pairs),
        "femicide_rates": femicide_rates,
        "bc_values": bc_values,
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "spearman_r": float(spearman_r),
        "spearman_p": float(spearman_p),
    }

    print("\n  --- BC vs femicide rate correlation ---")
    print(f"  Valid pairs : {result['n_pairs']}")
    print(
        f"  Pearson  r = {result['pearson_r']:.6f}  "
        f"(p = {result['pearson_p']:.4e})"
    )
    print(
        f"  Spearman r = {result['spearman_r']:.6f}  "
        f"(p = {result['spearman_p']:.4e})"
    )

    significance = "SIGNIFICANT" if result["spearman_p"] < 0.05 else "not significant"
    direction = "positive" if result["spearman_r"] > 0 else "negative"
    print(f"\n  Correlation is {direction} and {significance} (α = 0.05).")
    if result["spearman_p"] < 0.05:
        if result["spearman_r"] > 0:
            print("  → More central municipalities tend to have HIGHER femicide rates.")
        else:
            print("  → More central municipalities tend to have LOWER femicide rates.")
    else:
        print("  → No statistically detectable association between BC and femicide rate.")

    return result


def get_top_nodes(
    G: nx.Graph,
    betweenness: dict,
    count: int = TOP_NODES_COUNT,
) -> pd.DataFrame:
    rows = []
    for node, bc_value in betweenness.items():
        data = G.nodes[node]
        rows.append({
            "city": data.get("name", node),
            "geocode": data.get("geocodigo", node),
            "betweenness_centrality": bc_value,
            "femicide_rate_normalized": data.get("taxa_feminicidio_norm"),
        })

    top_nodes = (
        pd.DataFrame(rows)
        .sort_values("betweenness_centrality", ascending=False)
        .head(count)
        .reset_index(drop=True)
    )
    top_nodes.index += 1

    print(f"\n  --- Top {count} nodes by BC ---")
    print(
        top_nodes[["city", "betweenness_centrality", "femicide_rate_normalized"]].to_string()
    )

    return top_nodes


def plot_bc_distribution(
    values: np.ndarray,
    title: str,
    output_path: str | Path | None = None,
) -> None:
    fig, axis = plt.subplots(figsize=(8, 5))

    axis.hist(values, bins=50, color="#2b7bba", edgecolor="white", alpha=0.85)
    axis.axvline(
        values.mean(),
        color="red",
        linestyle="--",
        label=f"Mean = {values.mean():.4f}",
    )
    axis.axvline(
        np.median(values),
        color="orange",
        linestyle=":",
        label=f"Median = {np.median(values):.4f}",
    )
    axis.set_xlabel("Betweenness Centrality (normalized)", fontsize=11)
    axis.set_ylabel("Frequency", fontsize=11)
    axis.set_title(f"Betweenness Centrality Distribution\n{title}", fontsize=11)
    axis.legend(fontsize=9)
    axis.grid(True, alpha=0.3)

    plt.tight_layout()
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"  BC distribution saved to: {output_path}")
    plt.close()


def plot_bc_femicide_correlation(
    correlation: dict,
    title: str,
    output_path: str | Path | None = None,
) -> None:
    bc_values = correlation["bc_values"]
    femicide_rates = correlation["femicide_rates"]
    pearson_r = correlation["pearson_r"]
    pearson_p = correlation["pearson_p"]
    spearman_r = correlation["spearman_r"]

    fig, axis = plt.subplots(figsize=(8, 6))
    axis.scatter(
        bc_values,
        femicide_rates,
        alpha=0.4,
        s=12,
        color="#2b7bba",
        edgecolors="none",
    )

    if len(bc_values) > 2:
        slope, intercept = np.polyfit(bc_values, femicide_rates, 1)
        x_min, x_max = bc_values.min(), bc_values.max()
        axis.plot(
            [x_min, x_max],
            [slope * x_min + intercept, slope * x_max + intercept],
            color="red",
            linewidth=1.5,
        )

    axis.set_xlabel("Betweenness Centrality (normalized)", fontsize=11)
    axis.set_ylabel("Normalized femicide rate", fontsize=11)
    axis.set_title(
        f"{title}\n"
        f"Pearson r = {pearson_r:.4f} (p = {pearson_p:.2e})  |  "
        f"Spearman r = {spearman_r:.4f}",
        fontsize=11,
    )
    axis.grid(True, alpha=0.3)
    plt.tight_layout()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"  BC vs femicide rate scatter saved to: {output_path}")
    plt.close()


def plot_top_nodes(
    top_nodes: pd.DataFrame,
    title: str,
    output_path: str | Path | None = None,
) -> None:
    fig, axis = plt.subplots(figsize=(10, 6))

    colors = [
        "#d62728"
        if rate is not None and rate > 0.5
        else "#2b7bba"
        for rate in top_nodes["femicide_rate_normalized"]
    ]
    axis.barh(
        top_nodes["city"][::-1],
        top_nodes["betweenness_centrality"][::-1],
        color=colors[::-1],
        edgecolor="white",
        alpha=0.85,
    )

    axis.set_xlabel("Betweenness Centrality (normalized)", fontsize=11)
    axis.set_title(
        f"Top {TOP_NODES_COUNT} nodes by Betweenness Centrality\n{title}",
        fontsize=11,
    )

    legend_elements = [
        Patch(facecolor="#d62728", label="Femicide rate > 0.5"),
        Patch(facecolor="#2b7bba", label="Femicide rate ≤ 0.5"),
    ]
    axis.legend(handles=legend_elements, fontsize=9, loc="lower right")
    axis.grid(True, alpha=0.3, axis="x")
    plt.tight_layout()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"  Top nodes chart saved to: {output_path}")
    plt.close()


def save_results(
    G: nx.Graph,
    betweenness: dict,
    graph_name: str,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    if output_path is None:
        output_path = RESULTS_DIR / f"betweenness_{graph_name}.csv"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for node, data in G.nodes(data=True):
        rows.append({
            "node_id": node,
            "city": data.get("name", ""),
            "geocode": data.get("geocodigo", ""),
            "betweenness_centrality": betweenness.get(node, float("nan")),
            "femicide_rate_normalized": data.get("taxa_feminicidio_norm"),
            "degree": G.degree(node),
        })

    dataframe = pd.DataFrame(rows)
    dataframe = dataframe.sort_values("betweenness_centrality", ascending=False)
    dataframe["bc_rank"] = range(1, len(dataframe) + 1)
    dataframe.to_csv(output_path, index=False, float_format="%.8f")
    print(f"\nSaved results to: {output_path}  ({len(dataframe)} rows)")
    return dataframe


def build_correlation_row(graph_name: str, bc_result: dict, correlation: dict) -> dict:
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
        "nodes": bc_result.get("nodes"),
        "edges": bc_result.get("edges"),
        "bc_mean": bc_result.get("mean"),
        "bc_median": bc_result.get("median"),
        "bc_max": bc_result.get("max"),
        "n_pairs": correlation.get("n_pairs"),
        "pearson_r": correlation.get("pearson_r"),
        "pearson_p": correlation.get("pearson_p"),
        "spearman_r": correlation.get("spearman_r"),
        "spearman_p": correlation.get("spearman_p"),
        "significant_005": (
            correlation.get("spearman_p") < 0.05 if correlation.get("spearman_p") is not None else False
        ),
    }


def save_plots(
    graph_name: str,
    bc_result: dict,
    correlation: dict,
    top_nodes: pd.DataFrame,
) -> None:
    plot_bc_distribution(
        bc_result["values"],
        graph_name,
        output_path=RESULTS_DIR / f"bc_distribution_{graph_name}.png",
    )

    if correlation:
        plot_bc_femicide_correlation(
            correlation,
            graph_name,
            output_path=RESULTS_DIR / f"bc_correlation_{graph_name}.png",
        )

    plot_top_nodes(
        top_nodes,
        graph_name,
        output_path=RESULTS_DIR / f"bc_top_nodes_{graph_name}.png",
    )


def plot_correlation_comparison(correlation_df: pd.DataFrame) -> None:
    meso_df = correlation_df[correlation_df["scope"] == "mesoregion"].copy()
    if meso_df.empty:
        print("[WARNING] No mesoregion correlation results available for comparison plot.")
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
            subset.loc[subset["mesoregion_label"] == label, "spearman_r"].squeeze()
            if label in subset["mesoregion_label"].values
            else np.nan
            for label in order
        ]
        offset = (index - (len(graph_types) - 1) / 2) * bar_width
        axis.bar(
            x_positions + offset,
            values,
            width=bar_width,
            label=graph_type.replace("_", " "),
            alpha=0.85,
        )

    state_df = correlation_df[correlation_df["scope"] == "state"]
    for _, row in state_df.iterrows():
        if row["spearman_r"] is not None and not np.isnan(row["spearman_r"]):
            axis.axhline(
                row["spearman_r"],
                linestyle="--",
                linewidth=1.2,
                alpha=0.7,
                label=f"State {row['graph_type'].replace('_', ' ')}",
            )

    axis.axhline(0, color="black", linewidth=0.8, alpha=0.4)
    axis.set_xticks(x_positions)
    axis.set_xticklabels(order, rotation=45, ha="right")
    axis.set_ylabel("Spearman correlation (BC vs femicide rate)")
    axis.set_title("BC–Femicide Correlation by Mesoregion and Graph Type")
    axis.legend(fontsize=8, loc="best")
    axis.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    output_path = RESULTS_DIR / "bc_correlation_comparison_by_mesoregion.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Comparison plot saved to: {output_path}")


def save_correlation_summary(correlation_rows: list[dict]) -> pd.DataFrame:
    correlation_df = pd.DataFrame(correlation_rows)
    output_path = RESULTS_DIR / "betweenness_correlation_summary.csv"
    correlation_df.to_csv(output_path, index=False, float_format="%.6f")
    print(f"\nCorrelation summary saved to: {output_path}")

    state_summary = correlation_df[correlation_df["scope"] == "state"]
    meso_summary = correlation_df[correlation_df["scope"] == "mesoregion"]

    if not state_summary.empty:
        state_path = RESULTS_DIR / "betweenness_correlation_state_summary.csv"
        state_summary.to_csv(state_path, index=False, float_format="%.6f")
        print(f"State correlation summary saved to: {state_path}")

    if not meso_summary.empty:
        meso_path = RESULTS_DIR / "betweenness_correlation_mesoregion_summary.csv"
        meso_summary.to_csv(meso_path, index=False, float_format="%.6f")
        print(f"Mesoregion correlation summary saved to: {meso_path}")

    plot_correlation_comparison(correlation_df)
    return correlation_df


def analyze_graph(G: nx.Graph, graph_name: str, generate_plots: bool) -> dict:
    bc_result = calculate_betweenness(G)
    betweenness = bc_result["betweenness_centrality"]

    top_nodes = get_top_nodes(G, betweenness, count=TOP_NODES_COUNT)
    correlation = correlate_bc_with_femicide_rate(G, betweenness)

    save_results(G, betweenness, graph_name)

    if generate_plots:
        save_plots(graph_name, bc_result, correlation, top_nodes)

    return {
        "graph_name": graph_name,
        "bc_result": bc_result,
        "correlation": correlation,
        "top_nodes": top_nodes,
    }


def main() -> None:
    graph_paths = discover_graph_paths()
    correlation_rows = []

    for graph_name, graph_path in graph_paths.items():
        print("\n" + "=" * 60)
        print(f"  Graph: {graph_name}")
        print("=" * 60)

        G = read_graph(graph_path)
        metadata = parse_graph_name(graph_name)
        generate_plots = metadata["scope"] == "state"

        analysis = analyze_graph(G, graph_name, generate_plots=generate_plots)
        correlation_rows.append(
            build_correlation_row(
                graph_name,
                analysis["bc_result"],
                analysis["correlation"],
            )
        )

    if correlation_rows:
        save_correlation_summary(correlation_rows)


if __name__ == "__main__":
    main()
