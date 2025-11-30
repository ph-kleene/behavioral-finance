from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from paths import OUTPUT_FIGURE_DIR, OUTPUT_TABLE_DIR
from utils.data_loader import load_regression_results
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.alpha_heatmap")

ALPHA_MATRIX_CSV = OUTPUT_TABLE_DIR / "ff5_alpha_matrix.csv"
ALPHA_T_MATRIX_CSV = OUTPUT_TABLE_DIR / "ff5_alpha_t_matrix.csv"
FIG_PATH = OUTPUT_FIGURE_DIR / "alpha_heatmap.png"

SIZE_LABELS = [1, 2, 3, 4, 5]
BM_LABELS = [1, 2, 3, 4, 5]


def prepare_matrices(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert regression results into 5x5 matrices for alpha and t-stats.
    
    Args:
        df: Regression results DataFrame.
        
    Returns:
        Tuple of (alpha_matrix, t_matrix).
    """
    df["size_bin"] = df["portfolio"].str[1].astype(int)
    df["bm_bin"] = df["portfolio"].str[2].astype(int)
    df["alpha_pct"] = df["alpha"] * 100  # convert to percentage

    alpha_matrix = (
        df.pivot(index="bm_bin", columns="size_bin", values="alpha_pct")
        .reindex(index=BM_LABELS, columns=SIZE_LABELS)
    )
    t_matrix = (
        df.pivot(index="bm_bin", columns="size_bin", values="alpha_t")
        .reindex(index=BM_LABELS, columns=SIZE_LABELS)
    )
    alpha_matrix.index.name = "BM quintile"
    alpha_matrix.columns.name = "Size quintile"
    t_matrix.index.name = "BM quintile"
    t_matrix.columns.name = "Size quintile"
    return alpha_matrix, t_matrix


def plot_heatmap(alpha_matrix: pd.DataFrame, t_matrix: pd.DataFrame) -> None:
    """Plot heatmap of alphas with t-stats annotated."""
    annot = alpha_matrix.copy().astype(str)
    for i in range(alpha_matrix.shape[0]):
        for j in range(alpha_matrix.shape[1]):
            alpha_val = alpha_matrix.iloc[i, j]
            t_val = t_matrix.iloc[i, j]
            if pd.isna(alpha_val) or pd.isna(t_val):
                annot.iloc[i, j] = ""
            else:
                annot.iloc[i, j] = f"{alpha_val:.2f}%\n(t={t_val:.1f})"

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        alpha_matrix,
        annot=annot.values,
        fmt="",
        cmap="RdBu_r",
        center=0,
        cbar_kws={"label": "Monthly alpha (%)"},
    )
    plt.title("FF5 alpha heatmap (Size-BM 5x5)")
    plt.tight_layout()
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=200)
    plt.close()


def main() -> None:
    """Main entry point for alpha heatmap."""
    df = load_regression_results()
    alpha_matrix, t_matrix = prepare_matrices(df)
    write_csv(alpha_matrix.reset_index(), ALPHA_MATRIX_CSV, index=False)
    write_csv(t_matrix.reset_index(), ALPHA_T_MATRIX_CSV, index=False)
    plot_heatmap(alpha_matrix, t_matrix)
    LOGGER.info("Alpha heatmap saved to %s", FIG_PATH)


if __name__ == "__main__":
    main()
