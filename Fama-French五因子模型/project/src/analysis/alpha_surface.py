from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from paths import OUTPUT_FIGURE_DIR, OUTPUT_TABLE_DIR
from utils.data_loader import load_regression_results
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.alpha_surface")

SURFACE_HTML = OUTPUT_FIGURE_DIR / "alpha_surface.html"
GRID_CSV = OUTPUT_TABLE_DIR / "ff5_alpha_surface_grid.csv"

SIZE_LABELS = [1, 2, 3, 4, 5]
BM_LABELS = [1, 2, 3, 4, 5]


def build_grid(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert regression results into a grid for 3D plotting.
    
    Args:
        df: Regression results DataFrame.
        
    Returns:
        DataFrame grid of alpha percentages.
    """
    df["size_bin"] = df["portfolio"].str[1].astype(int)
    df["bm_bin"] = df["portfolio"].str[2].astype(int)
    df["alpha_pct"] = df["alpha"] * 100

    grid = (
        df.pivot(index="bm_bin", columns="size_bin", values="alpha_pct")
        .reindex(index=BM_LABELS, columns=SIZE_LABELS)
        .sort_index(ascending=True)
    )
    grid.index.name = "bm_bin"
    grid.columns.name = "size_bin"
    return grid


def create_surface(grid: pd.DataFrame) -> None:
    """Create and save 3D surface plot of alphas."""
    x = SIZE_LABELS
    y = BM_LABELS
    z = grid.values

    fig = go.Figure(
        data=[
            go.Surface(
                x=x,
                y=y,
                z=z,
                colorscale="RdBu",
                colorbar_title="alpha (%)",
                reversescale=True,
            )
        ]
    )
    fig.update_layout(
        title="3D surface of FF5 alphas (Size vs BM)",
        scene=dict(
            xaxis_title="Size quintile",
            yaxis_title="BM quintile",
            zaxis_title="Monthly alpha (%)",
        ),
        autosize=True,
    )
    OUTPUT_FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(SURFACE_HTML)


def main() -> None:
    """Main entry point for alpha surface plot."""
    df = load_regression_results()
    grid = build_grid(df)
    write_csv(grid.reset_index(), GRID_CSV, index=False)
    create_surface(grid)
    LOGGER.info("Alpha surface saved to %s", SURFACE_HTML)


if __name__ == "__main__":
    main()
