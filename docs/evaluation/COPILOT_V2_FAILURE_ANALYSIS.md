# Copilot V2 Remaining Failure Analysis

## Freeze and provenance

This analysis uses only the immutable `docs/evaluation/copilot/v2-real-run.json` record. It does not
replay a sample, persist Provider raw output, inspect an API key or overwrite V1/V2 evaluation files.

| Item | Frozen value |
| --- | --- |
| Provider model | `[K12]gemini-3.5-flash` |
| Temperature | 0 |
| Timeout | 60 seconds |
| Dataset | `dataset-v1.json`, version 1, 20 synthetic samples |
| V1 final | 13/20 |
| V2 final | 14/20 |
| Real BOSS / Nowcoder | 6/6 owner-reviewed PASS |

The V2 run received usable Provider content for 14 samples. All 14 finished with a valid V2 result,
43/43 grounded evidence and zero recorded safety or relevance violations. The six remaining samples
failed before any Copilot result content reached the parser.

## Per-sample findings

The approved A–L taxonomy does not include a dedicated transport or timeout category. These six are
therefore classified as `L. OTHER`, with a non-content subtype. “Raw result” is `NOT_RECEIVED`, not
redacted or guessed: the Provider adapter raised a sanitized transport error before returning Copilot
content. The security boundary intentionally does not retain an HTTP body, URL, envelope or raw error.

| Sample | Feature | First attempt raw result | Retry result | Validation error | Category | Layer | Root cause |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `copilot-001` | Match | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Provider unavailable | Provider | `AI_PROVIDER_UNAVAILABLE` after 2,029 ms; the sanitized record cannot distinguish upstream HTTP, URL or OS transport detail. |
| `copilot-005` | Match | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Timeout | Provider | `AI_TIMEOUT` after 60,536 ms; the request exceeded the frozen 60-second window. |
| `copilot-008` | Match | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Provider unavailable | Provider | `AI_PROVIDER_UNAVAILABLE` after 5,005 ms; no content was available to validate. |
| `copilot-009` | Resume Advice | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Provider unavailable | Provider | `AI_PROVIDER_UNAVAILABLE` after 5,004 ms; no content was available to validate. |
| `copilot-011` | Resume Advice | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Provider unavailable | Provider | `AI_PROVIDER_UNAVAILABLE` after 13,587 ms; no content was available to validate. |
| `copilot-012` | Resume Advice | `NOT_RECEIVED` | `NOT_RUN` | Parser/validator not reached | L. OTHER — Provider unavailable | Provider | `AI_PROVIDER_UNAVAILABLE` after 2,584 ms; no content was available to validate. |

### Category totals

| Category | Count |
| --- | ---: |
| A. NON_JSON | 0 |
| B. MARKDOWN_WRAPPER | 0 |
| C. JSON_PARSE_ERROR | 0 |
| D. MISSING_FIELD | 0 |
| E. WRONG_FIELD_TYPE | 0 |
| F. INVALID_ENUM | 0 |
| G. EVIDENCE_SOURCE_INVALID | 0 |
| H. EVIDENCE_GROUNDING_FAIL | 0 |
| I. UNSAFE_SUGGESTION | 0 |
| J. INTERVIEW_CATEGORY_MISMATCH | 0 |
| K. OUTPUT_TRUNCATED | 0 |
| L. OTHER — Provider unavailable | 5 |
| L. OTHER — Timeout | 1 |

### Layer totals

| Layer | Count | Evidence |
| --- | ---: | --- |
| Prompt | 0 | No failed sample returned content. |
| Schema | 0 | Schema validation was not reached. |
| Parser | 0 | JSON parsing was not reached. |
| Validator | 0 | Grounding/safety validation was not reached. |
| Retry | 0 | Only `AI_INVALID_RESPONSE` is eligible for one structure repair; transport/timeout correctly did not retry. |
| Provider / transport | 6 | Five unavailable errors and one 60-second timeout. |

No evidence supports calling these “Provider output randomness”: there was no output. The narrower and
defensible conclusion is Provider/transport availability variance during the frozen run.

## Structured-output chain review

| Check | Current behavior | Finding for these six failures |
| --- | --- | --- |
| JSON only | V2 prompts require JSON only; request also sends `response_format: json_object`. | Not reached. |
| Markdown fence cleanup | Product parser currently uses strict `json.loads` and does not strip fences. | No observed fence failure in these six. Changing this would not fix them. |
| Prefix/suffix extraction | Product parser does not extract JSON from explanatory prose. | No observed prefix/suffix failure in these six. |
| Schema nesting | V2 retains only fields used by Match, Resume Advice and Interview Prep UI. | 14/14 received V2 results passed final schema. No excessive-nesting evidence. |
| Enum | Interview categories are the approved PRODUCT/AI/TECHNICAL/PROJECT/BEHAVIORAL/DOMAIN set. | No Interview Prep sample failed. |
| Required fields | Exact fields match the persisted/UI contracts. | No missing-field failure in these six. |
| Array lengths | Empty grounded arrays are allowed; Interview Prep requires at least one job-grounded question. | No array-length failure in these six. |
| Repair | Exactly one structure-only repair occurs only after `AI_INVALID_RESPONSE`. | Correctly not triggered for unavailable/timeout. |
| Repair validation | Repaired content is parsed and grounded through the same strict validator. | Previously proven by `copilot-017`; not involved here. |
| Source IDs | Prompt carries the current allowlist; validator rejects unknown type/id/quote ownership. | 43/43 evidence in received V2 results; not reached by the six failures. |
| Suggestion safety | Unsafe fabricated-experience wording is rejected unless truth-conditional. | Zero recorded violation in received V2 results; not reached by the six failures. |

## Decision before code changes

There is no evidence-backed Prompt, Schema, Parser, Validator or repair change that can correct these
six failures while keeping the frozen Provider and timeout. Adding Markdown cleanup, relaxing enums or
changing required fields would be unrelated to the observed failure path and would weaken the causal
evaluation. Transport retry is also outside the existing approved rule and could duplicate a 60-second
optional request, so it is not introduced implicitly.

Therefore the minimum reliability fix at this checkpoint is **no product-code change**. The next safe
step is a fresh gated Provider run using the frozen model, temperature, timeout, dataset, Prompt V2,
Schema V2 and retry contract. This tests whether the observed availability burst was non-systemic without
changing the product to fit particular samples.

## Preflight selection constraint

The failed set contains three Match and three Resume Advice samples, but **zero Interview Prep failures**.
It is impossible to select one failed sample of each feature without fabricating history. The existing
fixed three-feature gate is retained:

- `copilot-001` — failed Match sample;
- `copilot-009` — failed Resume Advice sample;
- `copilot-017` — Interview Prep control and the only prior V2 sample that exercised bounded repair.

The gate must be 3/3 final PASS before the unchanged 20-sample rerun. If it fails, stop. If it passes,
write new output files rather than overwriting `v2-preflight.json` or `v2-real-run.json`.

## Historical decision before the later timeout-retry approval

- Failure analysis: COMPLETE.
- Product-code fix: NOT JUSTIFIED by the six observed failures.
- Provider preflight: PASS on 2026-09-16 in the project owner's configured PowerShell. The unchanged
  `copilot-001`/`009`/`017` gate reached first-pass and final Schema 3/3, evidence 10/10, zero safety or
  relevance violations and zero repair retries. The immutable record is
  `docs/evaluation/copilot/final-preflight.json`.
- Final rerun: COMPLETE. The owner ran all 20 unchanged samples after the 3/3 preflight; 18/20 passed first and final schema, 55/55 evidence was grounded, and no structure repair was used. `copilot-006` and `copilot-007` Match timed out at 60,403 ms and 60,473 ms. The former six V2 failures did not reproduce; two different samples exceeded the same frozen Provider window. This shows variable availability, not a proven Prompt/Schema/Parser/Validator defect. The exact upstream cause remains unknown. Record: `docs/evaluation/copilot/final-real-run.json`.
- Final product-code change: NONE; no evidence-backed fix within the frozen Provider/timeout/retry constraints. No cherry-picked rerun or threshold change.
- Verdict: `PHASE 11 BLOCKED`.
- Phase 12: NOT STARTED.

## Subsequent full-run outcome（2026-09-16）

The owner later approved one bounded retry only after `AI_TIMEOUT`, with the same 60s Provider timeout,
model, Prompt V2, Schema V2, dataset and scoring. The complete unchanged 20-sample run recorded in
`docs/evaluation/copilot/timeout-retry-real-run.json` reached 20/20 first/final PASS and 62/62 grounded
evidence. No retry was triggered; both formerly timed-out Match samples succeeded on the first attempt.
This is compatible with variable Provider availability but does not establish that the new retry caused
the improvement. The historical 18/20 and its two timeout failures remain preserved. With the prior
6/6 real-job owner review and all frozen acceptance gates satisfied, the latest verdict is
`PHASE 11 PASS`; Phase 12 was not started.
