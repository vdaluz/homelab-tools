#!/usr/bin/env python3
"""
Log anomaly detector: pulls logs from Loki, scores with Isolation Forest,
posts anomalies to Alertmanager.

Training window: last 6 hours (establishes "normal" baseline)
Scoring window: last 15 minutes (what we actually alert on)
"""

import re
import sys
import json
import logging
from datetime import datetime, timedelta, timezone

import requests
from sklearn.ensemble import IsolationForest
import numpy as np

LOKI_URL = "http://localhost:3100"
ALERTMANAGER_URL = "http://localhost:9093"
LOKI_QUERY = '{job=~".+"}'
TRAINING_HOURS = 6
SCORING_MINUTES = 15
TRAINING_LIMIT = 5000
SCORING_LIMIT = 500
CONTAMINATION = 0.05

# Lines matching any pattern are dropped before the model sees them, from both
# training and scoring windows. Use this to suppress known-benign log sources
# that score as anomalous due to unusual structure rather than actual problems.
# Patterns are Python regexes matched case-sensitively against the raw log line.
# To add a new exclusion: append a pattern here and re-run the cron job.
EXCLUSIONS = [
    # Loki self-monitoring: query performance metrics from the querier component
    r"caller=metrics\.go.*component=querier",
    # Grafana plugin update checker: periodic feature flag evaluation, always benign
    r"logger=plugins\.update\.checker.*flag evaluation succeeded",
    # Ansible uri/get_url health checks: logged when any playbook touches this host
    r"http_agent=ansible-httpget",
    # AppArmor denials: cosmetic LXC/dhclient profile mismatches, no functional impact
    r'apparmor="DENIED"',
    # cgroupsv2 inotify race: transient error when a Docker container stops mid-watch
    r"cgroupsv2\.Manager\.EventChan",
]

_EXCLUSION_RES = [re.compile(p) for p in EXCLUSIONS]


def is_excluded(line: str) -> bool:
    return any(r.search(line) for r in _EXCLUSION_RES)


# Keywords that indicate problems
BAD_KEYWORDS = [
    "error", "exception", "failed", "failure", "unauthorized",
    "forbidden", "timeout", "refused", "panic", "fatal", "critical",
    "traceback", "segfault", "killed", "oom",
]

_NUM_RE = re.compile(r"\b\d+\b")
_ID_RE = re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def normalize(line: str) -> str:
    line = _ID_RE.sub("<ID>", line)
    line = _NUM_RE.sub("<N>", line)
    return line.lower()


def extract_features(entries: list[tuple[str, str, dict]]) -> tuple[np.ndarray, list]:
    """
    entries: list of (timestamp_ns, line, stream_labels)
    Returns (feature_matrix, raw_entries)
    """
    freq: dict[str, int] = {}
    for ts_ns, line, _ in entries:
        key = normalize(line)
        freq[key] = freq.get(key, 0) + 1

    rows = []
    for ts_ns, line, labels in entries:
        ts_sec = int(ts_ns) / 1e9
        hour = datetime.fromtimestamp(ts_sec, tz=timezone.utc).hour

        raw_level = labels.get("level", labels.get("severity", "")).lower()
        if raw_level in ("error", "err", "fatal", "critical"):
            level = 2
        elif raw_level in ("warn", "warning"):
            level = 1
        else:
            level_from_text = line.lower()
            if any(w in level_from_text for w in ("error", "fatal", "critical", "panic")):
                level = 2
            elif any(w in level_from_text for w in ("warn", "warning")):
                level = 1
            else:
                level = 0

        keyword_hits = sum(1 for kw in BAD_KEYWORDS if kw in line.lower())
        msg_len = min(len(line), 500)
        msg_freq = freq.get(normalize(line), 1)

        rows.append([level, keyword_hits, msg_len, msg_freq, hour])

    return np.array(rows, dtype=float), entries


def query_loki(start: datetime, end: datetime, limit: int) -> list[tuple[str, str, dict]]:
    params = {
        "query": LOKI_QUERY,
        "start": str(int(start.timestamp() * 1e9)),
        "end": str(int(end.timestamp() * 1e9)),
        "limit": str(limit),
        "direction": "forward",
    }
    try:
        resp = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Loki query failed: %s", e)
        sys.exit(1)

    entries = []
    for stream in resp.json()["data"]["result"]:
        labels = stream["stream"]
        for ts_ns, line in stream["values"]:
            entries.append((ts_ns, line, labels))
    return entries


def post_alerts(anomalies: list[tuple[str, str, dict]]) -> None:
    # endsAt set to 20min from now so alerts survive until the next cron run.
    # Without this, alerts expire after resolve_timeout (5min) and re-fire every cycle.
    ends_at = (datetime.now(tz=timezone.utc) + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen: set[tuple[str, str]] = set()
    payload = []
    for ts_ns, line, labels in anomalies:
        job = labels.get("job", "unknown")
        host = labels.get("host", labels.get("hostname", "unknown"))
        key = (job, host)
        if key in seen:
            continue
        seen.add(key)
        payload.append({
            "labels": {
                "alertname": "LogAnomaly",
                "severity": "warning",
                "job": "log-anomaly-detector",
                "source_job": job,
                "host": host,
            },
            "annotations": {
                "summary": f"Anomalous log lines from {job} on {host}",
                "description": line[:500],
            },
            "endsAt": ends_at,
            "generatorURL": f"{LOKI_URL}/explore",
        })
    try:
        resp = requests.post(
            f"{ALERTMANAGER_URL}/api/v2/alerts",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        log.info("Posted %d anomaly alerts to Alertmanager", len(payload))
    except requests.RequestException as e:
        log.error("Alertmanager POST failed: %s", e)


def main() -> None:
    now = datetime.now(tz=timezone.utc)
    training_start = now - timedelta(hours=TRAINING_HOURS)
    scoring_start = now - timedelta(minutes=SCORING_MINUTES)

    log.info("Fetching training window (%dh, limit %d)...", TRAINING_HOURS, TRAINING_LIMIT)
    training_entries = [e for e in query_loki(training_start, now, TRAINING_LIMIT) if not is_excluded(e[1])]
    if len(training_entries) < 50:
        log.warning("Only %d training entries, skipping run (not enough data)", len(training_entries))
        sys.exit(0)

    log.info("Fetching scoring window (%dmin, limit %d)...", SCORING_MINUTES, SCORING_LIMIT)
    scoring_entries = [e for e in query_loki(scoring_start, now, SCORING_LIMIT) if not is_excluded(e[1])]
    if not scoring_entries:
        log.info("No log entries in scoring window, nothing to do")
        sys.exit(0)

    log.info("Training on %d entries, scoring %d entries", len(training_entries), len(scoring_entries))

    X_train, _ = extract_features(training_entries)
    X_score, _ = extract_features(scoring_entries)

    model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_jobs=1)
    model.fit(X_train)

    predictions = model.predict(X_score)
    anomaly_indices = np.where(predictions == -1)[0]

    if len(anomaly_indices) == 0:
        log.info("No anomalies detected")
        sys.exit(0)

    log.info("Detected %d anomalies", len(anomaly_indices))
    anomalies = [scoring_entries[i] for i in anomaly_indices]
    for _, line, labels in anomalies:
        log.info("  ANOMALY [%s]: %s", labels.get("job", "?"), line[:120])

    post_alerts(anomalies)


if __name__ == "__main__":
    main()
