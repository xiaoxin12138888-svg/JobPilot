# JD Structured AI Analysis

## Responsibility and boundary

Phase 6 adds one optional extraction use case for an already saved Job. The Web requests analysis,
FastAPI loads only the target Job, the application service calls one provider port, validates and
grounds the returned JSON, then persists one current result in SQLite. The Extension does not call
AI and is unchanged.

The outbound payload contains only title, company, description and optional location/salary text.
Notes, Applications, other Jobs, browser metadata, files and Resume data are outside the boundary.
The JD is wrapped as untrusted user data and never interpolated into the system instruction.

## Runtime configuration

All three process environment variables are required to enable analysis:

```text
JOBPILOT_LLM_BASE_URL=https://provider.example/v1
JOBPILOT_LLM_API_KEY=replace-locally
JOBPILOT_LLM_MODEL=provider-model-name
```

The API does not load `.env`. A missing, partial or invalid set leaves AI unconfigured without
preventing FastAPI startup. `baseUrl` must be an absolute HTTP(S) URL without credentials, query or
fragment. The adapter sends `POST {baseUrl}/chat/completions` with an explicit timeout. The API key
is never persisted or returned.

## Schema version 1

```text
JDAnalysis
  summary: string
  responsibilities: EvidenceItem[]
  mustHaveRequirements: EvidenceItem[]
  preferredRequirements: EvidenceItem[]
  skills: string[]
  experienceRequirements: EvidenceItem[]
  educationRequirements: EvidenceItem[]
  domainKeywords: string[]
  interviewFocus: EvidenceItem[]

EvidenceItem
  text: string
  evidence: string | null
```

Unknown/missing information becomes an empty string or array. Extra fields and wrong types fail
validation. Evidence whitespace is normalized and retained only when it is an exact substring of
the normalized description; unsupported evidence becomes `null`. No fuzzy matcher is used.

## Persistence and stale behavior

`jd_analysis_records` has a unique FK to `jobs`, schema version, canonical JSON, source input
fingerprint and timestamps. Reanalysis updates that row. GET compares the current five-field input
fingerprint with the stored fingerprint. A mismatch returns `isStale: true` while retaining the old
result; deleting the Job cascades to the record.

## API and failure behavior

- `GET /api/v1/jobs/{jobId}/analysis` returns configuration state and a nullable analysis.
- `POST /api/v1/jobs/{jobId}/analysis` accepts `{}` and creates or refreshes the analysis.
- Missing configuration: `503 AI_NOT_CONFIGURED`.
- timeout, network error, 429 or provider 5xx: `503 AI_PROVIDER_UNAVAILABLE`.
- malformed provider envelope/content or schema: `502 AI_INVALID_RESPONSE`.

All error messages are JobPilot-owned and omit raw provider data. Analysis failure never mutates an
existing result and never blocks Job/Application or capture operations.

## Evaluation

The de-identified samples and human-reviewed labels live in `docs/evaluation/jd-analysis/`. The
offline evaluator reports schema success, responsibility/must-have omissions and false extraction,
preferred misclassification, unsupported hallucinations and evidence grounding. Prompt V2 changes
must be traceable to observed V1 bad cases on the same dataset. Real results are recorded only when
a real configured Provider was actually run.
