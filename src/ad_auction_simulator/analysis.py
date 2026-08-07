from __future__ import annotations

import json
import os
from itertools import combinations
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats


def _deterministic_summary(kpis: pd.DataFrame, tests: pd.DataFrame) -> str:
    ranked = kpis.sort_values("revenue_per_auction", ascending=False).reset_index(drop=True)
    best = ranked.iloc[0]
    second = ranked.iloc[1]
    relative_lift = (
        (best.revenue_per_auction / second.revenue_per_auction - 1.0) * 100
        if second.revenue_per_auction
        else 0.0
    )
    primary = tests.sort_values("wilcoxon_p_value").iloc[0]
    significance = "statistically distinguishable" if primary.wilcoxon_p_value < 0.05 else "not statistically distinguishable"
    return (
        f"On the held-out synthetic auctions, {best.mechanism.replace('_', ' ')} produced the "
        f"highest mean revenue per auction ({best.revenue_per_auction:.3f} CPM), "
        f"{relative_lift:.1f}% above the next-best mechanism, while maintaining a "
        f"{best.fill_rate:.1%} fill rate. The strongest pairwise revenue difference was "
        f"{significance} under a paired two-sided Wilcoxon signed-rank test "
        f"(p={primary.wilcoxon_p_value:.3g}). These results describe this controlled "
        "simulation and should not be interpreted as production ad-market performance."
    )


def _optional_llm_summary(kpis: pd.DataFrame, tests: pd.DataFrame, fallback: str) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return fallback
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = (
            "Write one executive paragraph, at most 110 words, from the supplied auction "
            "simulation statistics. State that the data are synthetic and held out. Do not "
            "claim causality, production impact, or universal superiority. Mention revenue, "
            "fill rate, and the primary hypothesis-test result.\n\n"
            f"KPI table:\n{kpis.to_json(orient='records')}\n\n"
            f"Tests:\n{tests.to_json(orient='records')}"
        )
        response = client.responses.create(model=model, input=prompt)
        text = response.output_text.strip()
        return text or fallback
    except Exception as exc:  # Optional feature must never break the deterministic pipeline.
        return f"{fallback}\n\nAI summary generation was skipped: {type(exc).__name__}."


def analyze(database_path: Path, artifacts_path: Path, use_llm: bool = False) -> dict[str, object]:
    artifacts_path.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path), read_only=True) as connection:
        kpis = connection.execute("SELECT * FROM v_mechanism_kpis ORDER BY mechanism").df()
        revenue = connection.execute(
            """
            SELECT auction_id, mechanism, seller_revenue
            FROM fact_auction_outcomes
            WHERE split = 'evaluation'
            """
        ).df()
        placements = connection.execute("SELECT * FROM v_placement_mechanism_kpis").df()

    test_rows: list[dict[str, object]] = []
    revenue_wide = revenue.pivot(index="auction_id", columns="mechanism", values="seller_revenue")
    for mechanism_a, mechanism_b in combinations(sorted(revenue_wide.columns), 2):
        paired = revenue_wide[[mechanism_a, mechanism_b]].dropna()
        sample_a = paired[mechanism_a].to_numpy(float)
        sample_b = paired[mechanism_b].to_numpy(float)
        differences = sample_a - sample_b
        paired_t = stats.ttest_rel(sample_a, sample_b)
        try:
            wilcoxon = stats.wilcoxon(differences, alternative="two-sided", zero_method="wilcox")
            wilcoxon_statistic = float(wilcoxon.statistic)
            wilcoxon_p_value = float(wilcoxon.pvalue)
        except ValueError:
            wilcoxon_statistic = 0.0
            wilcoxon_p_value = 1.0

        nonzero = differences[differences != 0]
        if nonzero.size:
            ranks = stats.rankdata(np.abs(nonzero))
            positive_rank_sum = float(ranks[nonzero > 0].sum())
            negative_rank_sum = float(ranks[nonzero < 0].sum())
            rank_total = positive_rank_sum + negative_rank_sum
            matched_rank_biserial = (positive_rank_sum - negative_rank_sum) / rank_total
        else:
            matched_rank_biserial = 0.0
        difference_std = float(np.std(differences, ddof=1))
        cohens_dz = float(np.mean(differences) / difference_std) if difference_std else 0.0
        test_rows.append(
            {
                "mechanism_a": mechanism_a,
                "mechanism_b": mechanism_b,
                "paired_auctions": int(len(paired)),
                "mean_a": float(np.mean(sample_a)),
                "mean_b": float(np.mean(sample_b)),
                "mean_difference": float(np.mean(differences)),
                "skew_difference": float(stats.skew(differences)),
                "paired_t_statistic": float(paired_t.statistic),
                "paired_t_p_value": float(paired_t.pvalue),
                "wilcoxon_statistic": wilcoxon_statistic,
                "wilcoxon_p_value": wilcoxon_p_value,
                "matched_rank_biserial": matched_rank_biserial,
                "cohens_dz": cohens_dz,
                "primary_test": "wilcoxon_signed_rank",
            }
        )


    tests = pd.DataFrame(test_rows)
    deterministic = _deterministic_summary(kpis, tests)
    executive_summary = _optional_llm_summary(kpis, tests, deterministic) if use_llm else deterministic

    kpis.to_csv(artifacts_path / "mechanism_kpis.csv", index=False)
    tests.to_csv(artifacts_path / "hypothesis_tests.csv", index=False)
    placements.to_csv(artifacts_path / "placement_mechanism_kpis.csv", index=False)
    (artifacts_path / "executive_summary.md").write_text(executive_summary + "\n", encoding="utf-8")

    result = {
        "mechanism_kpis": kpis.to_dict(orient="records"),
        "hypothesis_tests": tests.to_dict(orient="records"),
        "executive_summary": executive_summary,
    }
    (artifacts_path / "analysis_summary.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return result
