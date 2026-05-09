# FTIAS Issue Triage Guide

## Purpose

This guide supports triage of FTIAS Internal Alpha / Technical Preview feedback. It helps maintainers classify peer-review feedback, reproducible defects, documentation gaps, responsible-use concerns, and future ideas without losing traceability.

## Triage Principles

- Preserve traceability.
- Prioritize safety/responsible-use concerns.
- Separate reproducible defects from usability feedback.
- Do not turn future ideas into implementation tasks until scoped.
- Keep engineering-support boundaries visible.

## Recommended Labels

These labels can be created manually in GitHub repository settings. GitHub API automation is not required.

| Label | Purpose |
|---|---|
| internal-alpha | Feedback from v0.1.0-alpha review |
| peer-review | Structured peer-review feedback |
| bug | Reproducible defect |
| enhancement | Feature or improvement request |
| documentation | README/manual/help/docs issue |
| safety-responsible-use | Boundary, overconfidence, certification/approval wording concern |
| data-ingestion | Upload, parsing, dataset versioning, failed cleanup |
| dashboard | Flight Test Detail dashboard/duration/window issue |
| parameters-charts | Parameter exploration, charts, event markers, comparison |
| ai-analysis | AI Analysis, prompt guard, deterministic mode selection |
| reports-export | PDF/report/export/provenance issue |
| frat | FRAT scoring, hard-stops, workflow, export |
| manual-help | Manual / Help page or PDF issue |
| repo-ci | CI, README, release, tags, repo hygiene |
| future-concept | Future idea not yet approved for implementation |
| vibration-frequency | Future vibration/frequency analysis concept |

## Severity Guidance

Use the issue template severity when available. If the template is incomplete, add a severity label or maintainer note.

- minor usability note
- documentation clarification
- workflow friction
- reproducible defect
- misleading result
- blocking issue
- safety/responsible-use concern

Safety/responsible-use concerns should be reviewed first, especially when output could be interpreted as certification approval, operational authorization, flutter clearance, loads substantiation, structural approval, or safety clearance.

## Triage Workflow

1. Confirm the issue has enough context.
2. Add the relevant workflow label.
3. Add a severity label or maintainer note.
4. Confirm provenance details are present when relevant:
   - dataset version
   - analysis job ID
   - FRAT assessment ID
   - report/export name
5. Decide one of:
   - fix now
   - clarify docs/manual
   - defer
   - convert to future concept
   - close as duplicate/not planned
6. Link related issues if applicable.

## Release Impact Decision

- Alpha blocker: must be resolved before the next internal alpha share or review cycle.
- Next alpha: should be targeted for the next alpha update, but does not block current review.
- Deferred: valid issue or improvement, but not needed for the current alpha scope.
- Future module: belongs to a larger concept or capability that needs separate design.
- Not planned: outside current project scope or not aligned with responsible-use boundaries.

## Examples

- FRAT hard-stop wording unclear -> labels: `peer-review`, `frat`, `documentation`
- Report exported with missing provenance -> labels: `bug`, `reports-export`
- Request for SRS module -> labels: `enhancement`, `future-concept`, `vibration-frequency`
- AI result sounds like approval -> labels: `safety-responsible-use`, `ai-analysis`
