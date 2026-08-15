#!/usr/bin/env python3
"""
Command-line entry point for the anomaly alert agent.

Pipeline: load CSV -> preprocess -> detect -> reason -> print + save JSON.
"""

import argparse
import json
import sys
from typing import List, Dict, Any

import pandas as pd

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from preprocessing import preprocess, CleanResult
from detectors import AnomalyEnsemble, Detection
from llm_backend import Reasoner

console = Console()

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
SEVERITY_COLOR = {
    "LOW": "yellow",
    "MEDIUM": "dark_orange",
    "HIGH": "red",
    "CRITICAL": "bold white on red",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anomaly Alert Agent")
    parser.add_argument(
        "--data",
        default="data/sensor_data.csv",
        help="Path to sensor data CSV (default: data/sensor_data.csv)",
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "groq", "offline"],
        default=None,
        help="Force a reasoning backend (default: auto-detect)",
    )
    parser.add_argument(
        "--min-severity",
        choices=list(SEVERITY_RANK.keys()),
        default="LOW",
        help="Minimum severity to display (default: LOW)",
    )
    parser.add_argument(
        "--json",
        default="alerts.json",
        help="Output JSON file (default: alerts.json)",
    )
    return parser.parse_args()


def load_data(path: str) -> pd.DataFrame:
    """Load CSV and parse timestamp."""
    return pd.read_csv(path, parse_dates=["timestamp"])


def run_pipeline(
    df: pd.DataFrame, backend: str | None
) -> tuple[CleanResult, List[Detection], List[Dict[str, Any]], str]:
    """Run preprocessing, detection, and reasoning.

    Returns the actual backend in use, not the one requested -- a status line
    must report observed state, never intended state.
    """
    clean_result = preprocess(df)

    ensemble = AnomalyEnsemble()
    ensemble.fit(clean_result.standardized)
    detections = ensemble.detect(clean_result.raw, clean_result.standardized)

    reasoner = Reasoner(prefer=backend)
    actual_backend = reasoner.backend

    alerts = []
    for det in detections:
        explanation = reasoner.explain(det)

        detected_by = []
        if det.rule_flag:
            detected_by.append("rules")
        if det.iforest_flag:
            detected_by.append("ml")
        detected_by_str = "+".join(detected_by) if detected_by else "none"

        alerts.append({
            "timestamp": det.timestamp,
            "severity": det.severity,
            "score": det.score,
            "values": det.values,
            "breached": [sig for sig, _dirn, _v in det.breached],
            "detected_by": detected_by_str,
            "diagnosis": explanation["diagnosis"],
            "recommended_action": explanation["action"],
        })

    return clean_result, detections, alerts, actual_backend


def filter_alerts(alerts: List[Dict], min_severity: str) -> List[Dict]:
    """Filter alerts by minimum severity."""
    min_rank = SEVERITY_RANK[min_severity]
    return [a for a in alerts if SEVERITY_RANK[a["severity"]] >= min_rank]


def print_header(clean_result: CleanResult, n_anomalies: int,
                 actual_backend: str, rows_read: int):
    """Print stage headers. `actual_backend` is what the Reasoner really chose."""
    report = clean_result.report
    console.rule("[bold blue]Anomaly Alert Agent[/bold blue]")
    console.print(f"Rows read from CSV: {rows_read}")
    console.print(
        f"Cleaning summary: duplicates removed={report['duplicates_removed']}, "
        f"missing values imputed={report['missing_values_imputed']}, "
        f"rows out={report['rows_out']}"
    )
    console.print(f"Anomalies flagged by detectors: {n_anomalies}")
    if actual_backend in ("ollama", "groq"):
        console.print(f"[magenta]reasoning: LLM - {actual_backend}[/magenta] "
                      f"[dim](free tier)[/dim]")
    else:
        console.print(
            "[yellow]reasoning: deterministic expert reasoner[/yellow] "
            "[dim](start Ollama or set GROQ_API_KEY for LLM reasoning)[/dim]"
        )


def print_summary_panel(alerts: List[Dict], rows_analysed: int):
    """Print summary panel with counts by severity."""
    total = len(alerts)
    by_sev = {sev: 0 for sev in SEVERITY_RANK}
    for a in alerts:
        by_sev[a["severity"]] += 1

    summary = Text()
    summary.append(f"Rows analysed: {rows_analysed}\n", style="bold")
    summary.append(f"Anomalies found: {total}\n")
    summary.append(f"Alerts emitted: {total}\n")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        summary.append(f"  {sev}: {by_sev[sev]}\n", style=SEVERITY_COLOR[sev])

    console.print(Panel(summary, title="Summary", border_style="blue",
                        box=box.ROUNDED))


def print_alerts_table(alerts: List[Dict]):
    """Print table of alerts."""
    table = Table(title="Alerts", box=box.SIMPLE_HEAVY, show_header=True,
                  header_style="bold magenta")
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Sev", style="bold", no_wrap=True)
    table.add_column("Score", justify="right", style="green")
    table.add_column("By", style="blue", no_wrap=True)
    table.add_column("temp", justify="right")
    table.add_column("press", justify="right")
    table.add_column("vib", justify="right")
    table.add_column("Breached", style="yellow")
    table.add_column("Recommended action", style="white", no_wrap=True,
                     overflow="ellipsis", max_width=40)

    for a in alerts:
        ts = a["timestamp"]
        time_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)
        vals = a["values"]
        breached = ", ".join(a["breached"]) if a["breached"] else "—"

        table.add_row(
            time_str,
            Text(a["severity"], style=SEVERITY_COLOR[a["severity"]]),
            f"{a['score']:.2f}",
            a["detected_by"],
            f"{vals['temp']:.1f}",
            f"{vals['pressure']:.3f}",
            f"{vals['vibration']:.3f}",
            breached,
            a["recommended_action"],
        )

    console.print(table)


def print_top_alert_panel(alerts: List[Dict]):
    """Print panel for the highest-priority alert."""
    if not alerts:
        console.print("[green]No alerts at or above the requested severity.[/green]")
        return

    top = max(alerts, key=lambda a: (SEVERITY_RANK[a["severity"]], a["score"]))

    content = Text()
    content.append("Diagnosis:\n", style="bold")
    content.append(f"{top['diagnosis']}\n\n")
    content.append("Recommended Action:\n", style="bold")
    content.append(top["recommended_action"])

    console.print(Panel(
        content,
        title=f"[bold]Top Alert — {top['severity']} (score: {top['score']:.3f})[/bold]",
        border_style=SEVERITY_COLOR[top["severity"]],
        box=box.ROUNDED,
    ))


def save_alerts_json(alerts: List[Dict], path: str):
    """Save alerts to JSON. default=str catches any stray Timestamp."""
    serializable = []
    for a in alerts:
        a_copy = dict(a)
        ts = a_copy["timestamp"]
        a_copy["values"] = {
            k: float(v) for k, v in a_copy["values"].items()
            if k in ("temp", "pressure", "vibration")
        }
        if hasattr(a_copy["score"], "item"):
            a_copy["score"] = a_copy["score"].item()
        serializable.append(a_copy)

    with open(path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    console.print(f"[green]Alerts saved to {path}[/green]")


def main():
    args = parse_args()

    try:
        df = load_data(args.data)
    except FileNotFoundError:
        console.print(f"[red]No such file: {args.data}[/red]")
        console.print("[dim]Run: python generate_data.py --rows 300 "
                      "--out data/sensor_data.csv --seed 42[/dim]")
        sys.exit(1)

    rows_read = len(df)

    # No broad try/except here on purpose. A real traceback names the file,
    # line and cause; "Pipeline error: <msg>" hides all three.
    clean_result, detections, alerts, actual_backend = run_pipeline(df, args.backend)

    filtered = filter_alerts(alerts, args.min_severity)

    print_header(clean_result, len(detections), actual_backend, rows_read)
    print_summary_panel(filtered, clean_result.report["rows_out"])
    print_alerts_table(filtered)
    print_top_alert_panel(filtered)
    save_alerts_json(filtered, args.json)


if __name__ == "__main__":
    main()
