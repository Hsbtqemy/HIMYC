"""Quality gate local/CI: pytest + couverture minimale.

Usage:
    python scripts/quality_gate.py --coverage-min 65
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str], cwd: Path, log_path: Path) -> int:
    """Exécute une commande, affiche le flux et l'écrit dans un log."""
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
        return process.wait()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quality gate pytest + coverage.")
    parser.add_argument(
        "--coverage-min",
        type=float,
        default=62.0,
        help="Seuil minimal de couverture totale (pourcentage).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("doc/audit/latest_quality_gate"),
        help="Dossier de sortie des logs/artefacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    coverage_json = output_dir / "coverage.json"
    pytest_log = output_dir / "pytest_cov.log"
    summary_path = output_dir / "summary.json"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--cov=src/howimetyourcorpus",
        f"--cov-report=json:{coverage_json}",
        "--cov-report=term",
    ]

    start = time.perf_counter()
    exit_code = run_command(cmd, cwd=repo_root, log_path=pytest_log)
    duration_s = round(time.perf_counter() - start, 3)

    total_coverage = None
    coverage_ok = False
    if coverage_json.exists():
        data = json.loads(coverage_json.read_text(encoding="utf-8"))
        total_coverage = float(data.get("totals", {}).get("percent_covered", 0.0))
        coverage_ok = total_coverage >= args.coverage_min

    summary = {
        "timestamp_utc": timestamp,
        "command": " ".join(cmd),
        "pytest_exit_code": exit_code,
        "duration_seconds": duration_s,
        "coverage_min": args.coverage_min,
        "total_coverage": total_coverage,
        "coverage_ok": coverage_ok,
        "pass": exit_code == 0 and coverage_ok,
        "artifacts": {
            "pytest_log": str(pytest_log.relative_to(repo_root)),
            "coverage_json": str(coverage_json.relative_to(repo_root)),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if exit_code != 0:
        print(f"\n[quality-gate] FAIL: pytest exit code = {exit_code}")
        return exit_code
    if not coverage_ok:
        print(
            "\n[quality-gate] FAIL: couverture insuffisante "
            f"({total_coverage:.2f}% < {args.coverage_min:.2f}%)"
        )
        return 2

    print(
        "\n[quality-gate] PASS: "
        f"tests OK, couverture {total_coverage:.2f}% >= {args.coverage_min:.2f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
