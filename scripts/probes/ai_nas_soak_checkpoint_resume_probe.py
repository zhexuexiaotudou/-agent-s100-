#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_soak_checkpoint_resume"


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return round(ordered[low] * (1 - weight) + ordered[high] * weight, 4)


def latency_summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "min_ms": round(min(values), 3) if values else None,
        "max_ms": round(max(values), 3) if values else None,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    inbox = personal / "Inbox"
    docs.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    for idx in range(8):
        (docs / f"2024_resume_packet_{idx:02d}.txt").write_text(
            f"Resume soak packet {idx}. Renovation payment invoice receipt amount {3000 + idx} CNY on 2024-05-{idx + 1:02d}.\n",
            encoding="utf-8",
        )
    (inbox / "resume_chat_screenshot_note.txt").write_text(
        "Chat screenshot note for resume soak. Payment receipt and approval pending.\n",
        encoding="utf-8",
    )
    return personal


def open_queue(path: Path) -> sqlite3.Connection:
    con = open_sqlite_connection(path, timeout=30, isolation_level=None, row_factory=True)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wave INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            lease_owner TEXT,
            lease_expires_at REAL,
            submitted_at REAL NOT NULL,
            started_at REAL,
            finished_at REAL,
            elapsed_ms REAL,
            result_json TEXT,
            error TEXT,
            idempotency_key TEXT NOT NULL UNIQUE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            phase TEXT NOT NULL,
            started_at REAL NOT NULL,
            finished_at REAL,
            elapsed_ms REAL,
            result_sha256 TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkpoint_name TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            previous_sha256 TEXT
        )
        """
    )
    return con


def digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def enqueue_jobs(queue_path: Path, waves: int, jobs_per_wave: int, started: float) -> list[int]:
    con = open_queue(queue_path)
    ids = []
    try:
        for wave in range(1, waves + 1):
            for idx in range(jobs_per_wave):
                task_type = "index" if idx % 4 == 0 else "search"
                query = "2024 renovation payment invoice receipt" if idx % 2 == 0 else "chat screenshot payment"
                payload = {"query": query, "wave": wave, "idx": idx}
                key = digest({"wave": wave, "idx": idx, "task_type": task_type, "payload": payload})[:24]
                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO jobs(wave, task_type, payload_json, status, submitted_at, idempotency_key)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (wave, task_type, json.dumps(payload, ensure_ascii=False), time.perf_counter() - started, key),
                )
                if cur.lastrowid:
                    ids.append(int(cur.lastrowid))
    finally:
        con.close()
    return ids


def write_checkpoint(queue_path: Path, name: str, previous_sha256: str | None = None) -> dict:
    con = open_queue(queue_path)
    try:
        counts = {
            row["status"]: row["count"]
            for row in con.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
        }
        payload = {
            "checkpoint_name": name,
            "generated_at": iso_now(),
            "counts": counts,
            "max_finished_job_id": con.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM jobs WHERE status='done'").fetchone()["max_id"],
            "pending_ids": [row["id"] for row in con.execute("SELECT id FROM jobs WHERE status='pending' ORDER BY id")],
            "running_ids": [row["id"] for row in con.execute("SELECT id FROM jobs WHERE status='running' ORDER BY id")],
            "done_ids": [row["id"] for row in con.execute("SELECT id FROM jobs WHERE status='done' ORDER BY id")],
        }
        payload_sha = digest(payload)
        con.execute(
            "INSERT INTO checkpoints(checkpoint_name, generated_at, payload_json, payload_sha256, previous_sha256) VALUES (?, ?, ?, ?, ?)",
            (name, payload["generated_at"], json.dumps(payload, ensure_ascii=False), payload_sha, previous_sha256),
        )
        payload["payload_sha256"] = payload_sha
        payload["previous_sha256"] = previous_sha256
        return payload
    finally:
        con.close()


def recover_running(queue_path: Path) -> list[dict]:
    con = open_queue(queue_path)
    recovered = []
    try:
        rows = con.execute("SELECT * FROM jobs WHERE status='running' ORDER BY id").fetchall()
        for row in rows:
            recovered.append({"job_id": row["id"], "lease_owner": row["lease_owner"], "attempts": row["attempts"]})
            con.execute(
                "UPDATE jobs SET status='pending', lease_owner=NULL, lease_expires_at=NULL, error=? WHERE id=?",
                ("recovered_from_checkpoint_resume", row["id"]),
            )
    finally:
        con.close()
    return recovered


def claim_job(queue_path: Path, owner: str, started: float) -> dict | None:
    con = open_queue(queue_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY wave, id LIMIT 1").fetchone()
        if not row:
            con.execute("COMMIT")
            return None
        now = time.perf_counter() - started
        con.execute(
            "UPDATE jobs SET status='running', attempts=attempts + 1, lease_owner=?, lease_expires_at=?, started_at=? WHERE id=?",
            (owner, time.monotonic() + 60, now, row["id"]),
        )
        con.execute(
            "INSERT INTO executions(job_id, idempotency_key, attempt, phase, started_at) VALUES (?, ?, ?, ?, ?)",
            (row["id"], row["idempotency_key"], int(row["attempts"]) + 1, owner, now),
        )
        exec_id = int(con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        con.execute("COMMIT")
        item = dict(row)
        item["attempts"] = int(row["attempts"]) + 1
        item["execution_id"] = exec_id
        return item
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def finish_job(queue_path: Path, job: dict, started: float, elapsed_ms: float, result: dict) -> None:
    con = open_queue(queue_path)
    result_sha = digest(result)
    try:
        now = time.perf_counter() - started
        con.execute(
            """
            UPDATE jobs
            SET status='done', finished_at=?, elapsed_ms=?, result_json=?, error=NULL,
                lease_owner=NULL, lease_expires_at=NULL
            WHERE id=?
            """,
            (now, round(elapsed_ms, 3), json.dumps(result, ensure_ascii=False), job["id"]),
        )
        con.execute(
            "UPDATE executions SET finished_at=?, elapsed_ms=?, result_sha256=? WHERE id=?",
            (now, round(elapsed_ms, 3), result_sha, job["execution_id"]),
        )
    finally:
        con.close()


def execute_job(job: dict, personal_root: Path, index_path: Path) -> dict:
    payload = json.loads(job["payload_json"])
    if job["task_type"] == "index":
        status = build_sqlite_inventory(personal_root, index_path)
        return {"task_type": "index", "file_count": status.get("file_count"), "failed_count": status.get("failed_count")}
    matches = search_sqlite_index(index_path, payload.get("query", ""), limit=8)
    return {
        "task_type": "search",
        "query": payload.get("query"),
        "match_count": len(matches),
        "top_path": matches[0]["relative_path"] if matches else None,
    }


def run_some(queue_path: Path, personal_root: Path, index_path: Path, started: float, phase: str, limit: int | None = None) -> list[dict]:
    processed = []
    while True:
        if limit is not None and len(processed) >= limit:
            break
        job = claim_job(queue_path, phase, started)
        if not job:
            break
        t0 = time.perf_counter()
        result = execute_job(job, personal_root, index_path)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        finish_job(queue_path, job, started, elapsed_ms, result)
        processed.append(
            {
                "job_id": job["id"],
                "idempotency_key": job["idempotency_key"],
                "attempt": job["attempts"],
                "phase": phase,
                "elapsed_ms": round(elapsed_ms, 3),
                "result": result,
            }
        )
    return processed


def simulate_crashed_running(queue_path: Path, started: float) -> int | None:
    con = open_queue(queue_path)
    try:
        row = con.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY wave, id LIMIT 1").fetchone()
        if not row:
            return None
        con.execute(
            "UPDATE jobs SET status='running', attempts=attempts + 1, lease_owner='simulated_crashed_soak_worker', lease_expires_at=?, started_at=? WHERE id=?",
            (time.monotonic() - 30, time.perf_counter() - started, row["id"]),
        )
        con.execute(
            "INSERT INTO executions(job_id, idempotency_key, attempt, phase, started_at) VALUES (?, ?, ?, 'pre_interrupt_crashed', ?)",
            (row["id"], row["idempotency_key"], int(row["attempts"]) + 1, time.perf_counter() - started),
        )
        return int(row["id"])
    finally:
        con.close()


def snapshot(queue_path: Path) -> dict:
    con = open_queue(queue_path)
    try:
        jobs = [dict(row) for row in con.execute("SELECT * FROM jobs ORDER BY id")]
        executions = [dict(row) for row in con.execute("SELECT * FROM executions ORDER BY id")]
        checkpoints = [dict(row) for row in con.execute("SELECT * FROM checkpoints ORDER BY id")]
    finally:
        con.close()
    for row in jobs:
        if row.get("payload_json"):
            row["payload"] = json.loads(row.pop("payload_json"))
        if row.get("result_json"):
            row["result"] = json.loads(row.pop("result_json"))
    for row in checkpoints:
        if row.get("payload_json"):
            row["payload"] = json.loads(row.pop("payload_json"))
    counts = {}
    for row in jobs:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"counts": counts, "jobs": jobs, "executions": executions, "checkpoints": checkpoints}


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS checkpoint/resume contract for interrupted continuous task soaks.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--waves", type=int, default=4)
    parser.add_argument("--jobs-per-wave", type=int, default=6)
    parser.add_argument("--pre-interrupt-jobs", type=int, default=7)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "soak_checkpoint_resume")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    index_path = run_dir / "soak_checkpoint_resume.sqlite3"
    queue_path = run_dir / "soak_checkpoint_resume_queue.sqlite3"
    build_sqlite_inventory(personal_root, index_path)
    started = time.perf_counter()
    enqueued = enqueue_jobs(queue_path, max(1, args.waves), max(1, args.jobs_per_wave), started)
    before_results = run_some(queue_path, personal_root, index_path, started, "pre_interrupt", max(1, args.pre_interrupt_jobs))
    crashed_job_id = simulate_crashed_running(queue_path, started)
    before_checkpoint = write_checkpoint(queue_path, "before_resume")
    recovered = recover_running(queue_path)
    recovery_checkpoint = write_checkpoint(queue_path, "after_recovery", before_checkpoint["payload_sha256"])
    after_results = run_some(queue_path, personal_root, index_path, started, "post_resume", None)
    final_checkpoint = write_checkpoint(queue_path, "final", recovery_checkpoint["payload_sha256"])
    state = snapshot(queue_path)
    all_results = before_results + after_results
    done_jobs = [job for job in state["jobs"] if job["status"] == "done"]
    unfinished = [job for job in state["jobs"] if job["status"] != "done"]
    completed_keys = [job["idempotency_key"] for job in done_jobs]
    duplicate_completed_keys = sorted({key for key in completed_keys if completed_keys.count(key) > 1})
    finished_execs = [item for item in state["executions"] if item.get("finished_at") is not None]
    elapsed_values = [float(item["elapsed_ms"]) for item in finished_execs if item.get("elapsed_ms") is not None]
    checkpoint_chain_ok = (
        len(state["checkpoints"]) == 3
        and state["checkpoints"][1].get("previous_sha256") == state["checkpoints"][0].get("payload_sha256")
        and state["checkpoints"][2].get("previous_sha256") == state["checkpoints"][1].get("payload_sha256")
    )
    failures = []
    if len(done_jobs) != len(enqueued):
        failures.append("done_job_count_mismatch")
    if unfinished:
        failures.append("unfinished_jobs_after_resume")
    if crashed_job_id is None:
        failures.append("crashed_running_job_not_simulated")
    if not recovered:
        failures.append("running_job_not_recovered")
    if duplicate_completed_keys:
        failures.append("duplicate_completed_idempotency_keys")
    if not checkpoint_chain_ok:
        failures.append("checkpoint_hash_chain_invalid")
    if not after_results:
        failures.append("post_resume_processed_no_jobs")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_soak_checkpoint_resume" if not failures else "failed_ai_nas_soak_checkpoint_resume",
        "scope": "bounded checkpoint/resume acceptance for interrupted continuous index/search soaks",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(index_path),
        "queue_path": str(queue_path),
        "config": {
            "waves": args.waves,
            "jobs_per_wave": args.jobs_per_wave,
            "pre_interrupt_jobs": args.pre_interrupt_jobs,
        },
        "summary": {
            "enqueued_jobs": len(enqueued),
            "pre_interrupt_completed": len(before_results),
            "simulated_crashed_job_id": crashed_job_id,
            "recovered_jobs": len(recovered),
            "post_resume_completed": len(after_results),
            "done_jobs": len(done_jobs),
            "unfinished_jobs": len(unfinished),
            "duplicate_completed_idempotency_keys": duplicate_completed_keys,
            "checkpoint_count": len(state["checkpoints"]),
            "checkpoint_hash_chain_valid": checkpoint_chain_ok,
            "execution_latency": latency_summary(elapsed_values),
            "failures": failures,
        },
        "recovered": recovered,
        "results": all_results,
        "state": state,
        "final_index_status": sqlite_index_status(index_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_files_created": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "network_call_performed": False,
            "writes": "isolated fixture files, SQLite index, SQLite queue/execution/checkpoint tables, and Markdown/JSON reports",
        },
        "production_gap": "Production should run the same checkpoint/resume contract against mounted NAS queues during long-duration OpenClaw/model-service load.",
    }
    json_path = run_dir / "soak_checkpoint_resume.json"
    md_path = run_dir / "soak_checkpoint_resume.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Soak Checkpoint Resume",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- enqueued_jobs: `{payload['summary']['enqueued_jobs']}`",
        f"- pre_interrupt_completed: `{payload['summary']['pre_interrupt_completed']}`",
        f"- simulated_crashed_job_id: `{crashed_job_id}`",
        f"- recovered_jobs: `{payload['summary']['recovered_jobs']}`",
        f"- post_resume_completed: `{payload['summary']['post_resume_completed']}`",
        f"- unfinished_jobs: `{payload['summary']['unfinished_jobs']}`",
        f"- checkpoint_hash_chain_valid: `{checkpoint_chain_ok}`",
        f"- execution_p95_ms: `{payload['summary']['execution_latency']['p95_ms']}`",
        f"- failures: `{failures}`",
        "- policy: isolated fixture queue/index only; no real Personal mutation and no service start",
        "",
        "## Checkpoints",
        "",
    ]
    for item in state["checkpoints"]:
        lines.append(
            f"- `{item['checkpoint_name']}` sha `{item['payload_sha256']}` previous `{item.get('previous_sha256')}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
