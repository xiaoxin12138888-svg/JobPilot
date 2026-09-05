# JD Analysis Evaluation Set

`dataset-v1.json` contains 20 synthetic, de-identified JDs written in realistic BOSS/Nowcoder
styles. It contains no account data, contacts, cookies, URLs or page HTML. Each sample has
human-reviewed gold labels for responsibilities, must-have, preferred, skills, experience and
education.

The project owner completed the item-by-item review on 2026-09-05. The dataset records
`goldReviewStatus: human-reviewed`, `reviewedSampleCount: 20`, and the same status on every sample;
the Chinese `GOLD_REVIEW_PACK.md` preserves the original candidate decisions and review history.
The evaluator requires all three signals and blocks a partial or top-level-only status change.

Run from the repository root after configuring the three Provider environment variables:

```text
uv run --project apps/api python apps/api/scripts/evaluate_jd_analysis.py \
  --dataset docs/evaluation/jd-analysis/dataset-v1.json \
  --output docs/evaluation/jd-analysis/prompt-v1-run.json
```

The runner sends each sample through the same V1 application prompt and infrastructure adapter as
the product. It persists only validated structured results and aggregate counters—never API keys,
provider envelopes or raw invalid responses. Text comparisons are exact after whitespace/case
normalization, so every reported omission/false extraction is auditable rather than model-judged.
`unsupportedHallucinationCount` is the conservative count of model-supplied evidence strings that
are not exact substrings of the normalized JD; schema failures remain separate.

Prompt V2 must not be created from hypothetical cases. First commit an actual V1 run, review its
sample-level differences, record real cases in `../JD_ANALYSIS_BAD_CASES.md`, then change the prompt
and rerun this identical dataset.
