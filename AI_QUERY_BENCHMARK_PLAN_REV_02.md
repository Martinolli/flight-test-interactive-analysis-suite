# AI Query Benchmark Plan — REV 02 (2026-04-11)

## Objective

Run repeatable A/B tests for `AI Standards Query` across different `.env` parameter profiles and identify the best operating profile for specialist flight-test engineering use.

This revision keeps the original benchmark structure, but improves:

- evaluation discipline
- failure detection
- comparison fairness
- practical execution speed
- decision usefulness

---

## Benchmark Principles

1. Compare profiles using the same document library state and the same question order.
2. Change one profile at a time.
3. Restart the backend after `.env` changes so the new settings are loaded.
4. Rebuild the backend only when dependencies, image contents, or Dockerfile-related behavior changes.
5. Score both answer quality and answer trustworthiness.
6. Penalize overclaiming, unsupported specificity, and weak uncertainty handling.

---

## Runtime Guidance

### When to restart vs rebuild

Use **restart** when you only change:

- `QUERY_LLM_MODEL`
- `QUERY_TEMPERATURE`
- `QUERY_MAX_TOKENS`
- retrieval parameters
- citation-density thresholds
- other `.env` runtime settings

Recommended command:

```bash
docker compose restart backend
```

Use **rebuild** only when you change:

- Python dependencies
- `requirements.txt`
- Dockerfile
- system packages
- code that is baked into the image and not live-mounted

Typical rebuild command:

```bash
docker compose up -d --build backend
```

---

## Run Protocol

1. Set one parameter profile in `.env`.
2. Restart backend:
   - `docker compose restart backend`
3. Confirm backend is healthy.
4. Ask all benchmark questions in the same order.
5. Apply the specified prompt variant for that run.
6. Record scores and notes immediately after each answer.
7. Repeat with next profile.

### Control Conditions

Keep these fixed during the benchmark:

- same indexed documents
- same user account
- same backend code revision
- same frontend build
- same question wording
- same scoring rubric
- same prompt variant order

---

## Evaluation Flow Per Question

For each answer, perform this sequence:

1. **Gate Check (Pass / Fail)**
   - Did it follow the prompt variant?
   - Did it keep inline citations when requested?
   - Did it avoid invented standards, evidence, or numeric claims?
   - Did it preserve requested structure?

2. **Scoring**
   - Score the dimensions below from 1 to 5.

3. **Risk Note**
   - Record whether the answer showed:
     - overclaim risk
     - weak citation grounding
     - generic wording
     - good uncertainty discipline
     - strong synthesis

4. **Usefulness Tag**
   - Mark best fit:
     - specialist brief
     - standards cross-check
     - risk review
     - uncertainty/gap assessment
     - procedure/test planning

---

## Scoring Rubric (1-5)

### Core Quality Dimensions

- `TechnicalDepth`: specialist-level reasoning vs generic wording
- `SourceAccuracy`: claims correctly supported by retrieved sources
- `MultiSourceSynthesis`: uses multiple relevant docs coherently
- `Actionability`: clear go/no-go criteria, mitigations, test steps
- `FormatCompliance`: follows requested structure (matrix, assumptions, gates)

### Reliability / Safety Dimensions

- `UncertaintyHandling`: clearly separates evidence, assumptions, blockers, and unknowns
- `OverclaimControl`: avoids pretending confidence beyond available evidence
- `Groundedness`: stays close to retrieved material instead of drifting into plausible but unsupported text

### Operational Dimension

- `Latency`: perceived response speed

### Optional Extra Notes

- `ReviewEffort`: how easy the answer is for an engineer to inspect quickly
- `BestUseCase`: where this profile performs best

---

## Quick Interpretation of Scores

### Quality Guidance

- **5** = excellent, specialist-ready
- **4** = strong, minor issues only
- **3** = useful but mixed
- **2** = weak, needs substantial caution
- **1** = poor or misleading

### Gate Rule

If an answer fails the gate check, mark:

- `Gate = Fail`
- still score it
- add the reason in Notes

A profile with frequent gate failures should not be selected as default even if some answers score highly.

---

## Parameter Profiles To Test

### Profile A — Specialist / High Quality

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

### Profile B — Balanced Baseline

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

### Profile C — Faster / Lower Cost

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

### Optional Noise-Reduction Overlay

Apply only after the baseline comparison if warnings feel too noisy:

```env
QUERY_WARNING_CITATION_DENSITY=0.30
```

---

## Benchmark Question Families

### A. Evidence Sufficiency / Readiness

1. Explain separation analysis for guided dummy stores and define minimum pre-flight evidence required before first release.
2. What evidence is required to claim safe envelope expansion from one release condition to the next?
3. Give a structured unknowns list when data is missing, separating critical blockers vs non-critical assumptions.

### B. Risk Framing / Decision Support

4. Build a preliminary qualitative risk matrix (5x5 likelihood/severity) for a campaign with no operational separation report.
5. For the same scenario, list explicit No-Go gates and objective release criteria that must be met before flight.
6. Draft a concise specialist brief to a Flight Test Review Board: readiness status, gaps, conditions to proceed, and decision recommendation.

### C. Standards / Concept Comparison

7. Compare jettison analysis vs operational separation analysis and explain why jettison-only evidence is insufficient.
8. Explain launch transient risks for guided stores and failure modes that can cause aircraft/store recontact.

### D. Procedure / Test Design

9. Provide a test-card sequence for risk reduction: ground checks -> captive carry -> incremental release envelope expansion.
10. Propose instrumentation requirements for first release campaign (aircraft + store + telemetry + video) and minimum sampling expectations.

### E. Uncertainty Drivers / Hazard Structure

11. Identify top uncertainty drivers in separation prediction (aero, mass properties, release dynamics, controls) and how to reduce each.
12. Provide an example hazard log with at least 8 hazards, initial risk, mitigations, residual risk, and verification method.

---

## Additional Challenge Questions

Use these after the main 12 if you want stronger model discrimination.

### Challenge 1 — Insufficient Evidence Discipline

Ask for a precise recommendation where the available documents are unlikely to support a definitive answer.
Goal:

- reward models that admit limits clearly
- penalize bluffing

### Challenge 2 — Multi-Document Comparison

Ask for a side-by-side comparison across multiple standards or guidance types.
Goal:

- measure synthesis quality

### Challenge 3 — Concise Expert Brief

Ask for a <=220 word specialist answer with dense technical meaning.
Goal:

- identify the best operational default profile

---

## Prompt Variants To Apply

Run each profile under both of these styles where practical.

### Variant S1 — Specialist concise

- `Answer for specialist audience, avoid generic wording.`
- `Use only inline [Sx] citations and cite each substantive claim.`
- `Return concise output <=220 words.`

### Variant S2 — Full technical detail

- `Answer for specialist audience, avoid generic wording.`
- `Use only inline [Sx] citations and cite each substantive claim.`
- `Return full detailed output with assumptions, method, and limits.`

### Variant S3 — Risk/decision style

Use on the risk questions:

- `Answer for specialist audience, avoid generic wording.`
- `Use only inline [Sx] citations and cite each substantive claim.`
- `Return assumptions, qualitative risk matrix, and explicit no-go gates.`

---

## Recommended Benchmark Matrix

Minimum practical benchmark:

- 3 profiles
- 12 questions
- 2 prompt styles

This gives:

- 72 scored responses

If that is too heavy, start with:

- Profiles A, B, C
- Questions 1, 4, 5, 7, 9, 12
- Variants S1 and S2

This reduced run still gives good discrimination.

---

## Selection Logic

At the end of testing, choose:

### Best default profile

Highest combination of:

- TechnicalDepth
- SourceAccuracy
- Groundedness
- OverclaimControl
- acceptable Latency

### Best concise profile

Highest performance in:

- S1 concise specialist mode
- low review effort
- strong actionability

### Best deep-analysis profile

Highest performance in:

- S2 full-detail mode
- synthesis + uncertainty handling

### Reject a profile if

- gate failures are frequent
- citations are often missing or weak
- answers overclaim beyond evidence
- outputs are consistently generic

---

## Results Template

| Q# | Family | Profile | Variant | Gate | TechnicalDepth | SourceAccuracy | MultiSourceSynthesis | Actionability | FormatCompliance | UncertaintyHandling | OverclaimControl | Groundedness | Latency | ReviewEffort | BestUseCase | Notes |
|----|--------|---------|---------|------|----------------|----------------|----------------------|---------------|------------------|---------------------|------------------|------------- |---------|--------------|-------------|-------|
| 1  | A      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 2  | A      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 3  | A      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 4  | B      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 5  | B      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 6  | B      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 7  | C      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 8  | C      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 9  | D      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 10 | D      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 11 | E      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |
| 12 | E      | A       | S1      |      |                |                |                      |               |                  |                     |                  |              |         |              |             |       |

Duplicate the block for:

- Profile A / S2
- Profile B / S1
- Profile B / S2
- Profile C / S1
- Profile C / S2

---

## Final Summary Template

At the end of benchmarking, write a short conclusion:

- **Best default profile:**
- **Best concise profile:**
- **Best deep-analysis profile:**
- **Weakest recurring failure:**
- **Most common overclaim pattern:**
- **Recommended production default:**
- **Recommended fallback / low-cost mode:**

---

## Practical Recommendation Before Starting

Start with:

- Profile A
- Profile B
- Profile C
- Questions 1, 4, 5, 7, 9, 12
- Variant S1 and Variant S2

Then expand only if the result is not clear.

This will save time while still giving a meaningful model comparison.
