# AI Query Benchmark Plan (2026-04-08)

## Objective

Run repeatable A/B tests for `AI Standards Query` across different `.env` parameter profiles.

## Run Protocol

1. Set one parameter profile in `.env`.
2. Recreate backend:
   - `docker compose up -d --force-recreate backend`
3. Ask all benchmark questions in the same order.
4. Record scores.
5. Repeat with next profile.

## Scoring (1-5)

- `TechnicalDepth`: specialist-level reasoning vs generic wording
- `SourceAccuracy`: claims correctly supported by retrieved sources
- `MultiSourceSynthesis`: uses multiple relevant docs coherently
- `Actionability`: clear go/no-go criteria, mitigations, test steps
- `FormatCompliance`: follows requested structure (matrix, assumptions, gates)
- `Latency`: perceived response speed

## Parameter Profiles To Test

### Profile A - Specialist / High Quality

```env
QUERY_LLM_MODEL=gpt-4o
QUERY_TEMPERATURE=0.05
QUERY_MAX_TOKENS=2200
QUERY_CONTEXT_LIMIT=14
QUERY_VECTOR_CANDIDATES=45
QUERY_LEXICAL_CANDIDATES=30
QUERY_MIN_UNIQUE_DOCUMENTS=4
QUERY_MAX_CHUNKS_PER_DOCUMENT=2
QUERY_MIN_CITATION_DENSITY=0.65
QUERY_WARNING_CITATION_DENSITY=0.40
QUERY_STRICT_CITATIONS=true
```

### Profile B - Balanced (Baseline)

```env
QUERY_LLM_MODEL=gpt-4o-mini
QUERY_TEMPERATURE=0.10
QUERY_MAX_TOKENS=1800
QUERY_CONTEXT_LIMIT=12
QUERY_VECTOR_CANDIDATES=30
QUERY_LEXICAL_CANDIDATES=20
QUERY_MIN_UNIQUE_DOCUMENTS=3
QUERY_MAX_CHUNKS_PER_DOCUMENT=3
QUERY_MIN_CITATION_DENSITY=0.60
QUERY_WARNING_CITATION_DENSITY=0.40
QUERY_STRICT_CITATIONS=true
```

### Profile C - Faster / Lower Cost

```env
QUERY_LLM_MODEL=gpt-4o-mini
QUERY_TEMPERATURE=0.15
QUERY_MAX_TOKENS=1200
QUERY_CONTEXT_LIMIT=9
QUERY_VECTOR_CANDIDATES=20
QUERY_LEXICAL_CANDIDATES=12
QUERY_MIN_UNIQUE_DOCUMENTS=2
QUERY_MAX_CHUNKS_PER_DOCUMENT=4
QUERY_MIN_CITATION_DENSITY=0.55
QUERY_WARNING_CITATION_DENSITY=0.35
QUERY_STRICT_CITATIONS=true
```

### Optional Noise-Reduction Variant (overlay on any profile)

```env
QUERY_WARNING_CITATION_DENSITY=0.30
```

## Systematic Benchmark Questions

1. Explain separation analysis for guided dummy stores and define minimum pre-flight evidence required before first release.
2. Build a preliminary qualitative risk matrix (5x5 likelihood/severity) for a campaign with no operational separation report.
3. For the same scenario, list explicit No-Go gates and objective release criteria that must be met before flight.
4. Compare jettison analysis vs operational separation analysis and explain why jettison-only evidence is insufficient.
5. Provide a test-card sequence for risk reduction: ground checks -> captive carry -> incremental release envelope expansion.
6. Identify top uncertainty drivers in separation prediction (aero, mass properties, release dynamics, controls) and how to reduce each.
7. Explain launch transient risks for guided stores and failure modes that can cause aircraft/store recontact.
8. Propose instrumentation requirements for first release campaign (aircraft + store + telemetry + video) and minimum sampling expectations.
9. Provide an example hazard log with at least 8 hazards, initial risk, mitigations, residual risk, and verification method.
10. Draft a concise specialist brief to a Flight Test Review Board: readiness status, gaps, conditions to proceed, and decision recommendation.
11. What evidence is required to claim safe envelope expansion from one release condition to the next?
12. Give a structured unknowns list when data is missing, separating critical blockers vs non-critical assumptions.

## Prompt Variants To Apply

- `Answer for specialist audience, avoid generic wording.`
- `Use only inline [Sx] citations and cite each substantive claim.`
- `Return concise output <=220 words.`
- `Return full detailed output with assumptions, method, and limits.`

## Results Template

| Q#  | Profile | TechnicalDepth | SourceAccuracy | MultiSourceSynthesis | Actionability | FormatCompliance | Latency | Notes |
| :-: | :-----: | :------------: | :------------: | :------------------: | :-----------: | :--------------: | :-----: | :---: |
|  1  |    A    |                |                |                      |               |                  |         |       |
|  2  |    A    |                |                |                      |               |                  |         |       |
|  3  |    A    |                |                |                      |               |                  |         |       |
|  4  |    A    |                |                |                      |               |                  |         |       |
|  5  |    A    |                |                |                      |               |                  |         |       |
|  6  |    A    |                |                |                      |               |                  |         |       |
|  7  |    A    |                |                |                      |               |                  |         |       |
|  8  |    A    |                |                |                      |               |                  |         |       |
|  9  |    A    |                |                |                      |               |                  |         |       |
| 10  |    A    |                |                |                      |               |                  |         |       |
| 11  |    A    |                |                |                      |               |                  |         |       |
| 12  |    A    |                |                |                      |               |                  |         |       |
