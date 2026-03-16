"""Checklist E2E assistee: execute des verifications automatisees et genere un rapport."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CheckGroup:
    key: str
    title: str
    checklist_refs: tuple[str, ...]
    tests: tuple[str, ...]


@dataclass
class RunResult:
    key: str
    title: str
    checklist_refs: list[str]
    command: list[str]
    returncode: int
    duration_s: float
    summary_line: str
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


CHECK_GROUPS: tuple[CheckGroup, ...] = (
    CheckGroup(
        key="scenario_a",
        title="Scenario A: Transcript -> Preparer -> Alignement -> Personnages",
        checklist_refs=(
            "A.4 Preparer transcript (edition + invalidation runs)",
            "A.5 Alignement phrases/tours + export",
            "A.6 Personnages propagation",
            "A.7 Concordance / exports",
        ),
        tests=(
            "tests/test_ui_preparer_navigation.py::test_preparer_save_transcript_structural_edits_replace_segments",
            "tests/test_ui_preparer_navigation.py::test_preparer_save_structural_warns_and_can_cancel_run_invalidation",
            "tests/test_ui_preparer_navigation.py::test_preparer_save_transcript_non_structural_keeps_align_runs",
            "tests/test_ui_alignement.py::test_run_align_episode_uses_selected_languages",
            "tests/test_ui_alignement.py::test_export_alignment_csv_writes_rows",
            "tests/test_ui_personnages.py::test_propagate_runs_with_utterance_assignments_when_run_is_utterance",
            "tests/test_ui_personnages.py::test_propagate_runs_and_reports_success",
            "tests/test_export_phase5.py::test_export_parallel_concordance_csv",
            "tests/test_export_phase5.py::test_export_align_report_html",
        ),
    ),
    CheckGroup(
        key="scenario_b",
        title="Scenario B: Sous-titres only",
        checklist_refs=(
            "B.3 Preparer source SRT + validation stricte",
            "B.4 Alignement SRT-only",
        ),
        tests=(
            "tests/test_ui_preparer_navigation.py::test_preparer_can_open_srt_source_when_track_exists",
            "tests/test_ui_preparer_navigation.py::test_preparer_srt_timecode_strict_rejects_overlap",
            "tests/test_ui_preparer_navigation.py::test_preparer_srt_timecode_overlap_allowed_when_strict_disabled",
            "tests/test_tasks_align_episode.py::test_align_episode_supports_cues_only_without_segments",
            "tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_prefers_existing_utterances_from_srt_source",
            "tests/test_ui_alignement.py::test_export_alignment_jsonl_writes_rows",
        ),
    ),
    CheckGroup(
        key="scenario_c",
        title="Scenario C: Continuite multi-langues projet",
        checklist_refs=("C.2 Langues coherentes entre onglets",),
        tests=(
            "tests/test_ui_preparer_navigation.py::test_refresh_language_combos_updates_multilang_tabs",
        ),
    ),
    CheckGroup(
        key="continuite",
        title="Continuite inter-onglets",
        checklist_refs=(
            "I.1 Preparer dirty + Ignorer recharge l'etat persistant",
            "I.2 Fin de job pipeline -> refresh onglets",
            "I.3 Handoff explicite vers Alignement",
        ),
        tests=(
            "tests/test_ui_preparer_navigation.py::test_preparer_discard_reloads_persisted_context",
            "tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_calls_concordance_refresh_speakers",
            "tests/test_ui_preparer_navigation.py::test_refresh_tabs_after_job_updates_personnages_runs",
            "tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_skips_duplicate_subs_refresh_when_inspector_is_combined",
            "tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_project_open_skips_duplicate_subs_refresh_when_inspector_is_combined",
            "tests/test_ui_mainwindow_core.py::test_tab_change_stays_on_preparer_when_prompt_cancelled",
            "tests/test_ui_mainwindow_core.py::test_open_preparer_for_episode_aborts_when_unsaved_cancelled",
            "tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_uses_utterance_when_transcript_rows_present",
            "tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_prefers_existing_utterances_from_srt_source",
        ),
    ),
)


def _last_non_empty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        raw = line.strip()
        if raw:
            return raw
    return ""


def _run_command(command: Sequence[str], *, cwd: Path) -> tuple[int, float, str, str]:
    started = time.perf_counter()
    proc = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    duration = time.perf_counter() - started
    return proc.returncode, duration, proc.stdout, proc.stderr


def _node_id_exists(repo_root: Path, node_id: str) -> bool:
    file_part, sep, test_name = node_id.partition("::")
    test_path = repo_root / file_part
    if not test_path.exists() or not test_path.is_file():
        return False
    if not sep:
        return True
    try:
        text = test_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return f"def {test_name}(" in text


def _select_existing_node_ids(repo_root: Path, node_ids: Sequence[str]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for node_id in node_ids:
        if node_id in seen:
            continue
        seen.add(node_id)
        if _node_id_exists(repo_root, node_id):
            selected.append(node_id)
    return selected


def _run_pytest(
    *,
    python_exe: str,
    cwd: Path,
    key: str,
    title: str,
    checklist_refs: Sequence[str],
    node_ids: Sequence[str],
) -> RunResult:
    command = [python_exe, "-m", "pytest", "-q", *node_ids]
    code, duration, stdout, stderr = _run_command(command, cwd=cwd)
    summary = _last_non_empty_line(stdout) or _last_non_empty_line(stderr) or f"returncode={code}"
    return RunResult(
        key=key,
        title=title,
        checklist_refs=list(checklist_refs),
        command=command,
        returncode=code,
        duration_s=duration,
        summary_line=summary,
        stdout=stdout,
        stderr=stderr,
    )


def _write_report_md(path: Path, *, started_at: datetime, results: Sequence[RunResult], overall_ok: bool) -> None:
    lines: list[str] = []
    lines.append("# Rapport Checklist E2E assistee")
    lines.append("")
    lines.append(f"- Date UTC: {started_at.isoformat()}")
    lines.append(f"- Statut global: {'PASS' if overall_ok else 'FAIL'}")
    lines.append(f"- Verifications executees: {len(results)}")
    lines.append("")

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"## {status} - {result.title}")
        lines.append("")
        lines.append(f"- Cle: `{result.key}`")
        lines.append(f"- Checklist: {', '.join(result.checklist_refs)}")
        lines.append(f"- Commande: `{' '.join(result.command)}`")
        lines.append(f"- Duree: {result.duration_s:.2f}s")
        lines.append(f"- Resume: `{result.summary_line}`")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report_json(path: Path, *, started_at: datetime, results: Sequence[RunResult], overall_ok: bool) -> None:
    payload = {
        "started_at_utc": started_at.isoformat(),
        "overall_ok": overall_ok,
        "checks": [
            {
                "key": r.key,
                "title": r.title,
                "checklist_refs": r.checklist_refs,
                "command": r.command,
                "returncode": r.returncode,
                "ok": r.ok,
                "duration_s": round(r.duration_s, 4),
                "summary_line": r.summary_line,
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-precheck",
        action="store_true",
        help="N'execute pas le pre-check global (pytest -q).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("doc/audit/latest_checklist_e2e_assist"),
        help="Dossier de sortie des rapports (md/json).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    started_at = datetime.now(timezone.utc)
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[RunResult] = []
    python_exe = sys.executable

    if not args.skip_precheck:
        results.append(
            _run_pytest(
                python_exe=python_exe,
                cwd=repo_root,
                key="precheck",
                title="Pre-check global (pytest -q)",
                checklist_refs=("Pre-check.1 base automatique",),
                node_ids=(),
            )
        )

    for group in CHECK_GROUPS:
        selected_node_ids = _select_existing_node_ids(repo_root, group.tests)
        if not selected_node_ids:
            results.append(
                RunResult(
                    key=group.key,
                    title=group.title,
                    checklist_refs=list(group.checklist_refs),
                    command=[python_exe, "-m", "pytest", "-q", *group.tests],
                    returncode=1,
                    duration_s=0.0,
                    summary_line="No available tests found for this scenario.",
                    stdout="",
                    stderr="No available tests found for this scenario.",
                )
            )
            continue
        results.append(
            _run_pytest(
                python_exe=python_exe,
                cwd=repo_root,
                key=group.key,
                title=group.title,
                checklist_refs=group.checklist_refs,
                node_ids=selected_node_ids,
            )
        )

    overall_ok = all(result.ok for result in results)
    report_md = output_dir / "report.md"
    report_json = output_dir / "report.json"
    _write_report_md(report_md, started_at=started_at, results=results, overall_ok=overall_ok)
    _write_report_json(report_json, started_at=started_at, results=results, overall_ok=overall_ok)

    print(f"[e2e-checklist] {'PASS' if overall_ok else 'FAIL'}")
    print(f"[e2e-checklist] rapport md: {report_md}")
    print(f"[e2e-checklist] rapport json: {report_json}")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[e2e-checklist] {status} {result.key}: {result.summary_line}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
