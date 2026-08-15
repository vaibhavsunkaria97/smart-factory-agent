# Smart Factory Agent

An AI-powered agent that monitors factory equipment sensor data (temperature,
pressure, vibration), detects anomalies using an ensemble of deterministic
threshold rules and an Isolation Forest model, and emits prioritised, actionable
alerts with plain-language diagnoses. The reasoning layer can optionally call a
local or hosted LLM, but works fully offline with a built-in deterministic
expert knowledge base — no API key required.

## Features

- **Rule + ML ensemble detection** — hard threshold rules catch known failure
  modes; Isolation Forest catches novel multivariate drift. Both vote; either
  can flag an anomaly.
- **Severity scoring** — each alert is scored 0–1 and classified as LOW /
  MEDIUM / HIGH / CRITICAL based on breach count and anomaly score.
- **LLM-augmented reasoning** — optional Ollama (local) or Groq (free tier)
  backend turns detections into human-readable diagnoses and recommended
  actions.
- **Deterministic fallback** — a maintenance knowledge base provides concrete
  diagnoses when no LLM is available. The agent never silently degrades.
- **Data preprocessing** — duplicate removal, missing-value imputation
  (time-based interpolation), z-score standardisation, all logged in a
  cleaning report.
- **Rich terminal output** — colour-coded severity, summary panel, alerts
  table, and top-alert detail via [Rich](https://github.com/Textualize/rich).
- **JSON export** — every run writes machine-readable alerts to a JSON file.
- **Evaluation harness** — precision, recall, F1, F2, confusion matrix, and
  precision-recall curve against ground-truth labels.
- **Reproducible synthetic data** — seeded generator with ~12 % anomaly rate,
  injected missing values, and duplicate timestamps.

## Requirements & Install

**Python 3.10+** is required.

```bash
pip install -r requirements.txt
```

Key dependencies: pandas, scikit-learn, matplotlib, rich, numpy, pytest.

## Quick Start

```bash
# 1. Generate synthetic sensor data
python generate_data.py --rows 300 --seed 42 --out data/sensor_data.csv

# 2. Run the agent
python agent.py

# 3. Evaluate detection quality against ground-truth labels
python evaluate.py

# 4. Run the test suite
pytest test_agent.py -v
```

## CLI Flags

### `agent.py`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--data` | path | `data/sensor_data.csv` | Path to sensor data CSV |
| `--backend` | choice | auto-detect | Force a reasoning backend (`ollama`, `groq`, `offline`) |
| `--min-severity` | choice | `LOW` | Minimum severity to display (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `--json` | path | `alerts.json` | Output JSON file for alerts |

### `generate_data.py`

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--rows` | int | `300` | Number of sensor readings to generate |
| `--seed` | int | `42` | Random seed for reproducibility |
| `--out` | path | `data/sensor_data.csv` | Output CSV path |

## Enabling a Real LLM Backend

The agent auto-detects available backends in priority order: Ollama → Groq →
offline. You can also force one with `--backend`.

### Ollama (local, offline)

```bash
ollama serve              # start the Ollama daemon
ollama pull llama3.2      # download a small model (~2 GB)
python agent.py           # auto-detects Ollama on localhost:11434
```

### Groq (free-tier hosted)

```bash
export GROQ_API_KEY="gsk_..."   # set your free Groq API key
python agent.py                 # auto-detects the key and uses Groq
```

> **Note:** Neither backend is required. When no LLM is reachable the agent
> falls back to a deterministic expert reasoner that maps each breach type to a
> concrete diagnosis and recommended action. No API key, no internet connection,
> no GPU needed.

## Project Layout

```
smart-factory-agent/
├── agent.py            # CLI entry point — orchestrates the full pipeline
├── preprocessing.py    # Data cleaning, imputation, z-score standardisation
├── detectors.py        # Rule detector, Isolation Forest, ensemble, severity scoring
├── llm_backend.py      # Ollama / Groq / offline reasoner with knowledge base
├── generate_data.py    # Synthetic sensor data generator with injected faults
├── evaluate.py         # Evaluation harness — P, R, F1, F2, PR curve, confusion matrix
├── test_agent.py       # Pytest suite covering generator, preprocessing, and detectors
├── requirements.txt    # Pinned Python dependencies
├── data/
│   └── sensor_data.csv # Generated sensor readings (not committed)
└── assets/
    └── evaluation.png  # Precision-recall curve and confusion matrix plot
```

## Offline by Default

The entire pipeline — data generation, preprocessing, detection, severity
scoring, diagnosis, and alert export — runs **fully offline** with zero
external dependencies beyond the Python packages in `requirements.txt`. The
deterministic fallback reasoner encodes real maintenance knowledge (coolant
flow, bearing wear, pressure leaks, etc.) so the agent produces actionable
output on an air-gapped factory floor, a CI server, or a laptop with no
internet. Connect an LLM when you want richer natural-language phrasing; the
detection logic itself never changes.
