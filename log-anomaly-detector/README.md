# Log Anomaly Detector

A Python script that scores Loki log lines with an Isolation Forest model and posts anything unusual to Alertmanager, so you don't have to hand-write a regex rule for every failure mode you haven't seen yet.

## Overview

Most log-based alerting means writing a rule for each specific error string you already know to watch for. This script takes a different approach: every run, it pulls a 6-hour "normal" window from Loki, trains an Isolation Forest on a handful of cheap features (log level, bad-keyword count, message length, message frequency, hour of day), then scores the last 15 minutes against that baseline. Anything that scores as an outlier gets posted to Alertmanager as a short-lived alert.

It's meant to run on a cron job every 15 minutes, matching the scoring window.

## Installation

1. Copy `detect-log-anomalies.py` to a host that can reach both your Loki and Alertmanager instances, and make it executable.
2. Install dependencies: `pip install requests scikit-learn numpy`.
3. Edit `LOKI_URL`, `ALERTMANAGER_URL`, and `LOKI_QUERY` at the top of the script to match your own environment.
4. Schedule it to run every 15 minutes:
   ```
   */15 * * * * /usr/bin/python3 /path/to/detect-log-anomalies.py
   ```

## Script Features

- **Isolation Forest scoring**: retrains on a fresh 6-hour baseline every run, no persisted model to go stale.
- **Feature extraction**: log level, bad-keyword hit count, message length, message frequency, and hour of day - cheap to compute, no embeddings or NLP.
- **Exclusion list**: a small set of regex patterns to drop known-benign noisy log sources before they ever reach the model.
- **Alertmanager integration**: deduplicates by `(job, host)` per run and posts short-lived alerts (`endsAt` ~20 minutes out) so they survive until the next cron tick without re-firing every cycle.

## Status

This script is retired from my own homelab as of September 2026. The `CONTAMINATION = 0.05` parameter forces the Isolation Forest to always flag roughly 5% of scored lines as anomalies, no matter how clean the actual log stream is. In practice that meant the exclusion list kept growing to chase down false positives, and it eventually reached several hundred regex patterns before I replaced this with a small set of hand-written Loki ruler alert rules that match the specific error/panic/segfault patterns I actually cared about.

The underlying technique still works and is a reasonable starting point if you want anomaly detection without writing a rule for every failure mode up front. Just don't pin `contamination` to a fixed value - drop it (scikit-learn defaults to `'auto'`) or tune it against your own false-positive tolerance, and budget time for exclusion-list upkeep either way.
