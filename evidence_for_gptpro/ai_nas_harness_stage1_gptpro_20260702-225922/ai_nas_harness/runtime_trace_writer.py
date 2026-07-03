from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .config_io import repo_root, safe_write_json, safe_write_text, utc_stamp


DEFAULT_SCHEMA_PATH = repo_root() / "db" / "runtime_trace_schema.sql"


class RuntimeTraceWriter:
    def __init__(self, db_path: str | Path, schema_path: str | Path = DEFAULT_SCHEMA_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path = Path(schema_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_schema(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as con:
            con.executescript(schema)
            con.commit()

    def start_run(self, scenario_id: str, user_request: str, workspace_id: str, metadata: dict[str, Any] | None = None) -> str:
        run_id = f"hr-{uuid.uuid4().hex[:16]}"
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO harness_runs(run_id, scenario_id, user_request, selected_workspace, status, started_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, scenario_id, user_request, workspace_id, "running", utc_stamp(), json.dumps(metadata or {}, ensure_ascii=False)),
            )
            con.commit()
        return run_id

    def finish_run(self, run_id: str, status: str, summary: dict[str, Any] | None = None) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE harness_runs SET status=?, finished_at=?, summary_json=? WHERE run_id=?",
                (status, utc_stamp(), json.dumps(summary or {}, ensure_ascii=False), run_id),
            )
            con.commit()

    def add_step(self, run_id: str, step_type: str, status: str, detail: dict[str, Any]) -> int:
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO harness_steps(run_id, step_type, status, created_at, detail_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, step_type, status, utc_stamp(), json.dumps(detail, ensure_ascii=False)),
            )
            con.commit()
            return int(cur.lastrowid)

    def add_workspace_decision(self, run_id: str, workspace_id: str, reason: str, confidence: float, alternatives: list[str]) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO workspace_decisions(run_id, workspace_id, reason, confidence, alternatives_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, workspace_id, reason, confidence, json.dumps(alternatives, ensure_ascii=False), utc_stamp()),
            )
            con.commit()

    def add_tool_call(
        self,
        run_id: str,
        workspace_id: str,
        tool_id: str,
        status: str,
        *,
        args: list[str] | None = None,
        result: dict[str, Any] | None = None,
        elapsed_ms: float | None = None,
        dispatcher_used: bool = True,
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO tool_calls(run_id, workspace_id, tool_id, status, args_json, result_json, elapsed_ms, dispatcher_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    workspace_id,
                    tool_id,
                    status,
                    json.dumps(args or [], ensure_ascii=False),
                    json.dumps(result or {}, ensure_ascii=False),
                    elapsed_ms,
                    1 if dispatcher_used else 0,
                    utc_stamp(),
                ),
            )
            con.commit()

    def add_policy_denial(self, run_id: str, workspace_id: str, tool_id: str, reason: str, requested_args: list[str] | None = None) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO policy_denials(run_id, workspace_id, tool_id, reason, requested_args_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, workspace_id, tool_id, reason, json.dumps(requested_args or [], ensure_ascii=False), utc_stamp()),
            )
            con.commit()

    def add_memory_read(self, run_id: str, workspace_id: str, memory_type: str, scope: str, privacy_level: str, record_count: int) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO memory_reads(run_id, workspace_id, memory_type, scope, privacy_level, record_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, workspace_id, memory_type, scope, privacy_level, record_count, utc_stamp()),
            )
            con.commit()

    def add_gate_result(self, run_id: str, gate_id: str, verdict: str, detail: dict[str, Any] | None = None) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO gate_results(run_id, gate_id, verdict, detail_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, gate_id, verdict, json.dumps(detail or {}, ensure_ascii=False), utc_stamp()),
            )
            con.commit()

    def table_counts(self) -> dict[str, int]:
        tables = [
            "harness_runs",
            "harness_steps",
            "workspace_decisions",
            "tool_calls",
            "policy_denials",
            "memory_reads",
            "gate_results",
        ]
        with self._connect() as con:
            return {table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def export_report(self, out_json: str | Path, out_md: str | Path) -> dict[str, Any]:
        with self._connect() as con:
            runs = [dict(row) for row in con.execute("SELECT * FROM harness_runs ORDER BY started_at, run_id")]
            denials = [dict(row) for row in con.execute("SELECT * FROM policy_denials ORDER BY created_at")]
            tools = [dict(row) for row in con.execute("SELECT * FROM tool_calls ORDER BY created_at")]
        payload = {
            "generated_at": utc_stamp(),
            "runtime_trace_db": str(self.db_path),
            "table_counts": self.table_counts(),
            "runs": runs,
            "tool_calls": tools,
            "policy_denials": denials,
        }
        safe_write_json(out_json, payload)
        lines = [
            "# AI-NAS Harness Runtime Trace",
            "",
            f"- generated_at: `{payload['generated_at']}`",
            f"- runtime_trace_db: `{payload['runtime_trace_db']}`",
            "",
            "## Table Counts",
            "",
        ]
        for key, value in payload["table_counts"].items():
            lines.append(f"- {key}: `{value}`")
        lines.extend(["", "## Runs", ""])
        for run in runs:
            lines.append(f"- `{run['run_id']}` scenario `{run['scenario_id']}` workspace `{run['selected_workspace']}` status `{run['status']}`")
        lines.extend(["", "## Policy Denials", ""])
        for denial in denials:
            lines.append(f"- `{denial['workspace_id']}` denied `{denial['tool_id']}`: {denial['reason']}")
        safe_write_text(out_md, "\n".join(lines) + "\n")
        return payload

