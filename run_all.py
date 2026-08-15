#!/usr/bin/env python3
"""
run_all.py
==========
One-command reproduction of the entire submission pipeline.

Steps
-----
1. Generate synthetic sensor data (generate_data.py)
2. Run the anomaly alert agent (agent.py)
3. Evaluate detectors against ground truth (evaluate.py)
4. Run the test suite (pytest)

If any step fails, the script prints the captured stdout/stderr and exits with
code 1. On success it prints a summary of the produced artifacts.
"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def run_step(cmd: List[str], step_name: str) -> Tuple[int, str, str]:
    """Run a command, capture output, and return (returncode, stdout, stderr)."""
    console.rule(f"[bold cyan]{step_name}[/bold cyan]")
    console.print(f"$ {' '.join(cmd)}", style="dim")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # we handle non-zero ourselves
        )
    except FileNotFoundError as e:
        console.print(f"[red]Command not found: {e}[/red]")
        return 1, "", str(e)

    # Print last 15 lines of stdout/stderr for visibility
    def tail(text: str, n: int = 15) -> str:
        lines = text.strip().splitlines()
        return "\n".join(lines[-n:]) if lines else ""

    if result.stdout:
        console.print(Panel(tail(result.stdout), title="stdout (tail)", border_style="green", box=box.ROUNDED))
    if result.stderr:
        console.print(Panel(tail(result.stderr), title="stderr (tail)", border_style="yellow", box=box.ROUNDED))

    return result.returncode, result.stdout, result.stderr


def check_artifacts() -> List[str]:
    """Return list of expected artifact paths that exist."""
    expected = [
        "data/sensor_data.csv",
        "alerts.json",
        "evaluation_results.json",
        "assets/evaluation.png",
    ]
    return [p for p in expected if Path(p).exists()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full anomaly-detection pipeline.")
    parser.add_argument("--rows", type=int, default=300, help="Rows to generate (default: 300)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the pytest step")
    args = parser.parse_args()

    steps = [
        (
            "Generate synthetic data",
            [
                sys.executable,
                "generate_data.py",
                f"--rows={args.rows}",
                f"--seed={args.seed}",
                "--out=data/sensor_data.csv",
            ],
        ),
        (
            "Run anomaly alert agent",
            [sys.executable, "agent.py"],
        ),
        (
            "Evaluate detectors",
            [sys.executable, "evaluate.py"],
        ),
    ]

    if not args.skip_tests:
        steps.append(
            (
                "Run test suite",
                [sys.executable, "-m", "pytest", "-q"],
            )
        )

    for step_name, cmd in steps:
        rc, out, err = run_step(cmd, step_name)
        if rc != 0:
            console.print(f"[bold red]Step failed: {step_name}[/bold red]")
            if out:
                console.print(Panel(out, title="Full stdout", border_style="red", box=box.ROUNDED))
            if err:
                console.print(Panel(err, title="Full stderr", border_style="red", box=box.ROUNDED))
            return 1

    # Success summary
    artifacts = check_artifacts()
    summary = Text()
    summary.append("All steps completed successfully.\n\n", style="bold green")
    summary.append("Artifacts produced:\n", style="bold")
    for art in artifacts:
        summary.append(f"  ✓ {art}\n", style="green")
    missing = [
        "data/sensor_data.csv",
        "alerts.json",
        "evaluation_results.json",
        "assets/evaluation.png",
    ]
    for art in missing:
        if art not in artifacts:
            summary.append(f"  ✗ {art} (missing)\n", style="red")

    console.print(Panel(summary, title="Pipeline Summary", border_style="blue", box=box.ROUNDED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
