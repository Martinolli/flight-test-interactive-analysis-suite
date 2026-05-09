# P5.2 Vibration & Frequency Analysis Concept

## Status

Future module concept. Not implemented in v0.1.0-alpha.

This note formalizes the idea captured in `Project_Documents/46_Frequency_Analysis_Tool_Suggested_Layout.md` so it can be planned as a bounded future engineering module. Existing FTIAS workflows remain unchanged.

## Purpose

The proposed module would provide a dedicated workspace for accelerometer, vibration, and frequency-domain review. It should help reviewers answer:

- What is vibrating?
- At what frequency?
- How strong is it?
- When does it happen?
- Which sensor or axis is most affected?
- Is it related to speed, landing, braking, gear movement, configuration, or other events?

The module should turn selected vibration channels into traceable engineering screening evidence through time-domain plots, frequency-domain plots, summary metrics, and data-quality warnings.

## Responsible-Use Boundary

This future module would be engineering screening and support only.

It must not be presented as:

- flutter clearance
- loads substantiation
- structural approval
- certification approval
- operational authorization or safety clearance

Outputs would depend on sampling rate, signal quality, units, time-window selection, preprocessing, sensor calibration, and analysis assumptions. Frequency-domain plots can look precise even when sampling, aliasing, synchronization, or unit problems make the result unreliable. The UI and exported reports should keep these limitations visible.

## Proposed User Workflow

1. Select flight test and dataset version.
2. Select sensor, channel, or accelerometer.
3. Select axis or resultant where applicable.
4. Select time window or event/phase window.
5. Review sampling rate, Nyquist frequency, and aliasing warning.
6. Choose preprocessing settings.
7. Run analysis.
8. Review time-domain and PSD results.
9. Review summary metrics and data-quality checks.
10. Export plots and summary.

## Proposed V1 Scope

V1 should stay intentionally bounded and deterministic.

Included inputs and controls:

- selected flight test
- selected dataset version
- selected channel or accelerometer
- selected axis or resultant
- selected time window
- sampling rate display
- Nyquist frequency display
- reliable frequency range warning
- remove mean
- detrend
- Hann window
- Welch PSD

Included outputs:

- time-domain plot
- PSD / ASD plot
- peak g
- peak-to-peak g
- RMS g
- crest factor
- dominant frequency
- frequency at maximum PSD
- basic band RMS

Basic data-quality checks:

- missing data
- constant value
- saturation suspicion
- sampling frequency too low
- aliasing risk
- unit ambiguity

## Proposed Later Scope

Later work can expand beyond the V1 screening module:

- FFT tab
- spectrogram
- comparison between sensors, axes, flights, configurations, and speeds
- custom frequency bands
- event-linked analysis
- speed/configuration correlation
- SRS / Shock Response Spectrum
- export-ready engineering report section
- integration with AI Analysis / deterministic vibration workflow

## Recommended Defaults

- Remove mean: ON
- Detrend: ON
- Window: Hann
- Overlap: 50%
- PSD method: Welch
- PSD as primary engineering output
- Sampling/Nyquist warning visible before analysis

## Data Quality and Sampling Warnings

Example display:

```text
Sampling rate: 256 Hz
Nyquist frequency: 128 Hz
Recommended reliable analysis range: up to approximately 80-100 Hz
```

The analysis should warn clearly when the sampling rate is too low for the requested frequency range. A conservative reliable range below the Nyquist frequency is preferred because filters, windowing, sensor response, and noise can reduce practical confidence near the theoretical limit.

Low sampling rate, missing data, saturation, bias, wrong units, and aliasing can all make plots appear convincing while the results are unreliable. These checks should be shown before or alongside the analysis output rather than hidden in export metadata.

## Relationship to Existing FTIAS Capabilities

Current Parameters charting:

- Provides general telemetry exploration and charting.
- Does not provide a dedicated vibration/frequency-domain workflow.
- The future module should reuse dataset/channel selection concepts where practical, but should not overload the general Parameters page.

Current Vibration & Loads deterministic workflow:

- Provides bounded deterministic screening support.
- The future module would add a focused signal-analysis workspace for vibration channels and frequency-domain evidence.
- It should not change existing deterministic semantics until a dedicated design and tests exist.

Current Flutter Support Pre-screen:

- Remains a pre-screening workflow only, not flutter clearance.
- Frequency-domain evidence may support review context in the future, but it must not be presented as clearance or substantiation.

Future real event markers:

- Event-linked windows would be useful for landing, braking, gear movement, configuration changes, and other phases.
- Until backend-derived event markers exist, event-linked analysis should be treated as future scope.

Report export:

- Future report integration should include plots, summary metrics, selected preprocessing settings, data-quality warnings, dataset/version provenance, and responsible-use boundaries.
- Existing report exports remain unchanged by this concept note.

## Proposed Roadmap Breakdown

These are future planning tasks, not active implementation tasks:

- P5.3 - Vibration/Frequency data model and API design
- P5.4 - Time-domain + PSD MVP
- P5.5 - Data-quality checks and sampling warnings
- P5.6 - Frequency bands and summary metrics
- P5.7 - Spectrogram and comparison mode
- P5.8 - Export/report integration
