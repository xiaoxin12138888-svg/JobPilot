# JD Analysis Evaluation Results

## Dataset

- Sample count: 20
- Source style: 10 BOSS-like and 10 Nowcoder-like synthetic, de-identified JDs
- Gold label method: candidate labels prepared; independent human review pending
- Fixed dataset version: 1

## Prompt V1

- Schema success: BLOCKED — Provider not configured
- Responsibilities omissions / false extraction: BLOCKED
- Must-have omissions / misclassification: BLOCKED
- Preferred misclassification: BLOCKED
- Unsupported hallucinations: BLOCKED
- Evidence grounding: BLOCKED

## Bad Cases

BLOCKED — no real V1 output exists, so no case is fabricated.

## Prompt V2

BLOCKED — V2 may only be driven by reviewed V1 Bad Cases. No V2 prompt or result is claimed.

## Acceptance blockers

1. A human reviewer must approve or correct every candidate gold label.
2. The project owner must provide a reachable OpenAI-compatible base URL, API key and model through
   the local FastAPI process environment.
3. V1 must run on the fixed dataset; observed cases must drive V2; the same dataset must then rerun.
4. One saved real BOSS Job and one saved real Nowcoder Job must be manually reviewed in the Web UI.
