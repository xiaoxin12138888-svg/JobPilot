# JD Analysis Evaluation Set

`dataset-v1.json` contains 20 synthetic, de-identified JDs written in realistic BOSS/Nowcoder
styles. It contains no account data, contacts, cookies, URLs or page HTML. Each sample has candidate
gold labels for responsibilities, must-have, preferred, skills, experience and education.

The dataset is currently marked `pending-human-review`. An AI-authored candidate label is not called
human-reviewed. Before a baseline is valid, the product owner or another human reviewer must inspect
every label against the JD and change the top-level value to `human-reviewed` in a reviewed commit.

Run from the repository root after that review and after configuring the three Provider environment
variables:

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
