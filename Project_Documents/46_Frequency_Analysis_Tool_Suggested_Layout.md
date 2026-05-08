# Frequency Analysis Tool — suggested layout

## 1. Data input panel

User selects:

```text
Sensor / accelerometer
Axis: X, Y, Z, or resultant
Sampling frequency
Start time / end time
Flight phase or event window
```

Very important: show a warning if the selected sampling frequency is too low.

Example:

```text
Sampling rate: 256 Hz
Nyquist frequency: 128 Hz
Recommended reliable analysis range: up to ~80–100 Hz
```

---

## 2. Pre-processing panel

Include simple options:

```text
Remove mean / bias
Detrend signal
High-pass filter
Low-pass filter
Band-pass filter
Window type
Segment length
Overlap percentage
```

Default suggestion:

```text
Remove mean: ON
Detrend: ON
Window: Hann
Overlap: 50%
PSD method: Welch
```

---

## 3. Analysis modes

I would create four tabs:

```text
Time Domain
FFT
PSD / ASD
Spectrogram
```

Later, you can add:

```text
SRS - Shock Response Spectrum
```

For the first version, I would prioritize:

```text
1. Time Domain
2. PSD
3. Spectrogram
4. FFT
```

PSD should be the “main engineering” output.

---

## 4. Automatic results summary

This would make your tool feel powerful.

For each selected signal, calculate:

```text
Peak g
Peak-to-peak g
RMS g
Dominant frequency
Frequency at maximum PSD
Band RMS
Crest factor
```

Example output:

```text
Sensor: LG_Z_ACC
Window: Touchdown + 5 sec
Peak acceleration: 2.8 g
RMS acceleration: 0.42 g
Dominant frequency: 17.5 Hz
Maximum PSD: 17.5 Hz
Crest factor: 6.67
```

That summary will help the engineer interpret the plot quickly.

---

## 5. Frequency bands

I’d allow the user to define custom bands.

Example:

```text
0–5 Hz
5–10 Hz
10–30 Hz
30–80 Hz
80–120 Hz
```

Then calculate RMS per band.

This is very useful because sometimes the total RMS is acceptable, but one frequency band is growing due to shimmy, resonance, brake vibration, or hardpoint excitation.

---

## 6. Comparison mode

This is where the tool becomes very useful.

Allow comparison between:

```text
Different sensors
Different axes
Different flights
Different test points
Different aircraft configurations
Different speeds
```

For example:

```text
Landing Gear Z axis — Flight 01 vs Flight 02
Hardpoint Y axis — Clean configuration vs Store installed
PSD at 80 kt vs 120 kt vs 160 kt
```

That is exactly the kind of thing flight-test people love because it turns raw data into engineering evidence.

---

## Recommended first implementation

For version 1, I would implement this:

```text
Upload / select accelerometer data
→ select sensor and axis
→ select time window
→ remove mean and detrend
→ plot time history
→ calculate RMS and peak g
→ calculate PSD using Welch
→ identify dominant frequency peaks
→ show spectrogram
→ export plots and summary table
```

That’s already a strong tool.

## One important design idea

Add a small “data quality check” before analysis:

```text
Sampling frequency OK?
Signal saturated?
Missing data?
Constant value?
Wrong units?
Aliasing risk?
Bias too high?
```

This will save a lot of trouble later. In flight-test analysis, bad conclusions often start with bad signal assumptions. The plot looks beautiful, but the data is betraying you with a smile — classic villain behavior.

## Best name inside your project

Something like:

```text
Frequency Analysis
```

or more specific:

```text
Accelerometer Frequency Analysis
```

or even:

```text
Vibration Analysis Module
```

My favorite would be:

```text
Vibration & Frequency Analysis
```

because it clearly tells the user what the tool is for.

Your standalone tool should not only plot frequencies; it should answer:

```text
What is vibrating?
At what frequency?
How strong is it?
When does it happen?
Which sensor/axis is most affected?
Is it related to speed, landing, braking, gear movement, or configuration?
```

That is the engineering value.
