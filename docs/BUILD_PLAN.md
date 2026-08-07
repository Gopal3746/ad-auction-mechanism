# Iterative build and commit plan

This is a suggested development sequence. Use it only as you actually complete and verify each step.

## Commit 1 — simulator foundation

```text
feat: add reproducible auction and bidder simulation
```

- configure bidder, advertiser, and placement populations
- generate private values and auction depth
- write raw Parquet outputs
- add deterministic random seed

## Commit 2 — auction mechanisms

```text
feat: implement first-price second-price and sample-reserve auctions
```

- replay identical auctions under each mechanism
- calculate allocation, payment, shading, and bidder surplus
- add mechanism unit tests

## Commit 3 — warehouse model

```text
feat: add star-schema transformation and DuckDB load
```

- create dimensions and bidder-level fact table
- add auction-level outcome fact table
- enforce data-quality checks

## Commit 4 — SQL metrics

```text
feat: add reusable auction KPI views
```

- fill rate
- revenue per auction
- bid spread and top-bid gap
- auction depth
- bid shading by depth
- placement-level results

## Commit 5 — statistical analysis

```text
feat: add paired mechanism hypothesis tests
```

- paired t-test
- Wilcoxon signed-rank test
- effect sizes
- machine-readable analysis artifacts

## Commit 6 — dashboard and documentation

```text
feat: add Streamlit dashboard and project documentation
```

- dashboard filters and KPI cards
- schema and architecture diagrams
- tracked sample results
- source citations and methodology limitations

## Commit 7 — optional AI summary and CI

```text
feat: add constrained AI summary and automated checks
```

- deterministic fallback
- environment-variable configuration
- GitHub Actions test workflow
- `.env` exclusion
