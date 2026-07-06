from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .conflict_policy import unique_target_rel
from .executor import execute_copy, execute_move, rollback_move
from .ai_index_resolver import SOURCE_PRIORITY
from .naming_policy import normalize_rel, path_hash, suggest_name
from .planner import collect_source_files
from .rollback import write_rollback_manifest
from .schema import connect, migrate


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLAGS_PATH = REPO_ROOT / "configs" / "auto_organizer_feature_flags.json"
DEFAULT_SECRET = "digua-auto-organizer-controlled-move-v1"
RAW_PATH_MARKERS = ("/mnt/nas/", "C:\\", "F:\\", "/home/", "/root/")


class AutoOrganizerService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        personal_root: str | Path,
        report_root: str | Path,
        flags_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.personal_root = Path(personal_root)
        self.report_root = Path(report_root)
        self.flags_path = Path(flags_path) if flags_path else DEFAULT_FLAGS_PATH
        self.flags = _read_json(self.flags_path)

    def status(self) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            plan_count = conn.execute("SELECT count(*) FROM auto_organize_plans").fetchone()[0]
            executed_count = conn.execute("SELECT count(*) FROM auto_organize_items WHERE status='executed'").fetchone()[0]
            rolled_back_count = conn.execute("SELECT count(*) FROM auto_organize_items WHERE status='rolled_back'").fetchone()[0]
            recent_state = self._recent_state(conn)
        finally:
            conn.close()
        return {
            "ok": bool(self.flags.get("auto_organize_enabled", True)),
            "schema": "digua_auto_organizer_v1",
            "plan_count": plan_count,
            "executed_item_count": executed_count,
            "rolled_back_item_count": rolled_back_count,
            "controlled_move_enabled": bool(self.flags.get("auto_organize_allow_move", True)),
            "controlled_rename_enabled": bool(self.flags.get("auto_organize_allow_rename", True)),
            "uncontrolled_move_enabled": False,
            "uncontrolled_rename_enabled": False,
            "delete_enabled": False,
            "overwrite_enabled": False,
            "rollback_required": bool(self.flags.get("auto_organize_rollback_required", True)),
            "allowed_source_roots": list(self.flags.get("auto_organize_allowed_source_roots") or ["Uploads", "待整理"]),
            "target_root": str(self.flags.get("auto_organize_target_root") or "AI整理"),
            "ai_driven_classification_enabled": True,
            "classification_priority": SOURCE_PRIORITY,
            "fallback_default_blocked": True,
            "diagnostic_fallback_flag": "allow_filename_fallback_for_diagnostic",
            "last_ai_driven_plan": recent_state.get("last_ai_driven_plan"),
            "last_fallback_blocker": recent_state.get("last_fallback_blocker"),
            "last_rollback_status": recent_state.get("last_rollback_status"),
            "qwen_execution_authority": False,
            "cloud_private_raw_egress": False,
            "raw_path_returned": False,
        }

    def create_plan(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        mode = str(payload.get("mode") or "move_and_rename")
        source_root = normalize_rel(str(payload.get("source_root") or "Uploads"))
        target_root = normalize_rel(str(payload.get("target_root") or self.flags.get("auto_organize_target_root") or "AI整理"))
        delete_original = bool(payload.get("delete_original", False))
        if not self.flags.get("auto_organize_enabled", True):
            return self._error("auto_organize_disabled")
        if mode not in {"move_and_rename", "copy"}:
            return self._error("unsupported_mode")
        if mode == "move_and_rename" and not (self.flags.get("auto_organize_allow_move", True) and self.flags.get("auto_organize_allow_rename", True)):
            return self._error("controlled_move_or_rename_disabled")
        if delete_original:
            return self._error("delete_original_forbidden")
        if source_root not in self._allowed_source_roots():
            return self._error("source_root_not_allowlisted")
        if target_root != normalize_rel(str(self.flags.get("auto_organize_target_root") or "AI整理")):
            return self._error("target_root_not_allowlisted")
        allow_filename_fallback = bool(payload.get("allow_filename_fallback_for_diagnostic"))
        max_items = int(payload.get("limit") or self.flags.get("auto_organize_max_items_per_plan") or 50)
        files = collect_source_files(self.personal_root, source_root, limit=max_items, source_rel_paths=payload.get("source_rel_paths"))
        plan_id = "plan_" + uuid.uuid4().hex[:16]
        created_at = _now()
        reserved: set[str] = set()
        items: list[dict[str, Any]] = []
        fallback_blockers: list[dict[str, Any]] = []
        max_file_bytes = int(self.flags.get("auto_organize_max_file_bytes") or 52_428_800)
        for path in files:
            if path.stat().st_size > max_file_bytes:
                continue
            source_rel = self._rel(path)
            name = suggest_name(path, source_rel, report_root=self.report_root, personal_root=self.personal_root)
            basis = name.get("classification_basis") if isinstance(name.get("classification_basis"), dict) else {}
            fallback_used = bool(name.get("fallback_used") or basis.get("fallback_used"))
            if fallback_used and not allow_filename_fallback:
                fallback_blockers.append(
                    {
                        "asset_id": name.get("asset_id"),
                        "source_rel": source_rel,
                        "source_hash": path_hash(source_rel),
                        "ai_driven": False,
                        "resolution_source": name.get("resolution_source") or basis.get("resolution_source") or "fallback_filename",
                        "fallback_used": True,
                        "fallback_available": True,
                        "blocker": name.get("blocker") or basis.get("blocker") or "ai_index_missing_for_asset",
                        "classification_basis": basis,
                        "naming_basis": name.get("naming_basis") or {},
                        "raw_path_returned": False,
                    }
                )
                continue
            if fallback_used and allow_filename_fallback:
                basis["diagnostic_fallback_allowed"] = True
                basis["product_demo_allowed"] = False
                name["classification_basis"] = basis
            category = normalize_rel(str(name["category_zh"]))
            target_rel = unique_target_rel(
                self.personal_root,
                f"{target_root}/{category}/{name['suggested_filename_zh']}",
                reserved,
            )
            source_sha = _sha256_file(path)
            item_id = "item_" + uuid.uuid4().hex[:16]
            item = {
                "item_id": item_id,
                "plan_id": plan_id,
                "asset_id": name["asset_id"],
                "source_rel": source_rel,
                "source_hash": path_hash(source_rel),
                "source_sha256": source_sha,
                "target_category_zh": category,
                "category_zh": category,
                "target_rel": target_rel,
                "target_hash": path_hash(target_rel),
                "original_filename": path.name,
                "suggested_filename_zh": name["suggested_filename_zh"],
                "final_filename": Path(target_rel).name,
                "operation": mode,
                "status": "planned",
                "ai_driven": bool(name.get("ai_driven") and not fallback_used),
                "resolution_source": str(name.get("resolution_source") or basis.get("source") or ""),
                "fallback_used": fallback_used,
                "classification_basis": name["classification_basis"],
                "naming_basis": name["naming_basis"],
                "conflict_policy": "auto_suffix_target_if_exists_no_overwrite",
                "rollback_available": True,
                "target_exists": (self.personal_root / target_rel).exists(),
            }
            items.append(item)
        if fallback_blockers and not allow_filename_fallback:
            return self._public(
                {
                    "ok": False,
                    "schema": "digua_auto_organizer_plan_v1",
                    "degraded": True,
                    "blocker": "ai_index_missing_for_asset",
                    "fallback_available": True,
                    "fallback_used": True,
                    "fallback_default_blocked": True,
                    "item_count": 0,
                    "items": fallback_blockers[:100],
                    "raw_path_returned": False,
                }
            )
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO auto_organize_plans(plan_id,source_root,target_root,mode,status,item_count,created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (plan_id, source_root, target_root, mode, "planned", len(items), created_at),
            )
            for item in items:
                conn.execute(
                    """
                    INSERT INTO auto_organize_items(
                      item_id,plan_id,asset_id,source_rel,source_hash,source_sha256,target_category_zh,
                      target_rel,target_hash,original_filename,suggested_filename_zh,final_filename,
                      operation,status,classification_basis_json,naming_basis_json,conflict_policy,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        item["item_id"],
                        item["plan_id"],
                        item["asset_id"],
                        item["source_rel"],
                        item["source_hash"],
                        item["source_sha256"],
                        item["target_category_zh"],
                        item["target_rel"],
                        item["target_hash"],
                        item["original_filename"],
                        item["suggested_filename_zh"],
                        item["final_filename"],
                        item["operation"],
                        item["status"],
                        json.dumps(item["classification_basis"], ensure_ascii=False, sort_keys=True),
                        json.dumps(item["naming_basis"], ensure_ascii=False, sort_keys=True),
                        item["conflict_policy"],
                        created_at,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return self._public(
            {
                "ok": True,
                "schema": "digua_auto_organizer_plan_v1",
                "plan_id": plan_id,
                "mode": mode,
                "delete_original": False,
                "item_count": len(items),
                "approval_required": True,
                "approval_phrase": self._approval_phrase(plan_id),
                "items": items[:100],
                "controlled_move_enabled": mode == "move_and_rename",
                "controlled_rename_enabled": mode == "move_and_rename",
                "delete_enabled": False,
                "overwrite_enabled": False,
                "fallback_default_blocked": True,
                "diagnostic_fallback_allowed": allow_filename_fallback,
                "raw_path_returned": False,
            }
        )

    def dry_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self._plan(payload)
        if not plan.get("ok"):
            return plan
        items = []
        for item in plan["items"]:
            source = self.personal_root / item["source_rel"]
            target = self.personal_root / item["target_rel"]
            items.append(
                {
                    **item,
                    "source_exists": source.exists() and source.is_file(),
                    "target_exists": target.exists(),
                    "source_sha256_current": _sha256_file(source) if source.exists() and source.is_file() else None,
                    "would_execute": source.exists() and source.is_file() and not target.exists(),
                    "rollback_available": True,
                }
            )
        return self._public({"ok": True, "schema": "digua_auto_organizer_dry_run_v1", "plan_id": plan["plan"]["plan_id"], "items": items, "raw_path_returned": False})

    def approve(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(payload.get("plan_id") or "")
        phrase = str(payload.get("approval_phrase") or "")
        if phrase != self._approval_phrase(plan_id):
            return self._error("approval_phrase_mismatch")
        token = self._approval_token(plan_id)
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            updated = conn.execute(
                "UPDATE auto_organize_plans SET status='approved', approved_by=?, approval_mode='typed_phrase', approved_at=? WHERE plan_id=? AND status IN ('planned','approved')",
                (str(payload.get("approved_by") or "operator"), _now(), plan_id),
            ).rowcount
            conn.commit()
        finally:
            conn.close()
        if not updated:
            return self._error("plan_not_found_or_not_approvable")
        return self._public({"ok": True, "plan_id": plan_id, "status": "approved", "approval_token": token, "raw_path_returned": False})

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self._plan(payload, include_private=True)
        if not plan.get("ok"):
            return plan
        plan_row = plan["plan"]
        plan_id = plan_row["plan_id"]
        if plan_row["status"] not in {"approved", "executed"}:
            return self._error("plan_not_approved")
        token = str(payload.get("approval_token") or "")
        if token and not hmac.compare_digest(token, self._approval_token(plan_id)):
            return self._error("approval_token_invalid")
        executed: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        reserved: set[str] = set()
        for item in plan["items"]:
            if item["status"] == "executed":
                executed.append(item)
                continue
            source = self.personal_root / item["source_rel"]
            target_rel = unique_target_rel(self.personal_root, item["target_rel"], reserved)
            target = self.personal_root / target_rel
            error = self._pre_execute_error(source, target, item)
            if error:
                errors.append({"item_id": item["item_id"], "error": error})
                continue
            try:
                if item["operation"] == "copy":
                    execute_copy(source, target)
                else:
                    execute_move(source, target)
                target_sha = _sha256_file(target)
            except Exception as exc:
                errors.append({"item_id": item["item_id"], "error": f"{type(exc).__name__}:{exc}"})
                continue
            rollback_payload = {
                "operation": item["operation"],
                "source_rel": item["source_rel"],
                "target_rel": target_rel,
                "source_sha256": item["source_sha256"],
                "target_sha256": target_sha,
                "restore_policy": "restore_original_or_rollback_prefixed_if_conflict",
            }
            item_public = {**item, "target_rel": target_rel, "target_sha256": target_sha, "rollback": rollback_payload, "status": "executed"}
            executed.append(item_public)
            self._mark_item_executed(item["item_id"], target_rel, rollback_payload)
        manifest_path = write_rollback_manifest(self.report_root, plan_id, {"plan_id": plan_id, "items": [item.get("rollback") for item in executed if item.get("rollback")]})
        self._mark_plan_executed(plan_id, bool(errors))
        return self._public(
            {
                "ok": not errors and bool(executed),
                "schema": "digua_auto_organizer_execute_v1",
                "plan_id": plan_id,
                "status": "executed" if not errors else "partial",
                "executed_count": len(executed),
                "error_count": len(errors),
                "errors": errors,
                "items": executed,
                "rollback_manifest": str(manifest_path.relative_to(self.report_root)),
                "move_allowed_controlled": True,
                "rename_allowed_controlled": True,
                "delete_allowed": False,
                "overwrite_allowed": False,
                "raw_path_returned": False,
                "qwen_execution_authority": False,
            }
        )

    def rollback(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan = self._plan(payload, include_private=True)
        if not plan.get("ok"):
            return plan
        plan_id = plan["plan"]["plan_id"]
        restored: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for item in reversed(plan["items"]):
            if item["status"] != "executed":
                continue
            rollback_info = json.loads(item.get("rollback_json") or "{}")
            target = self.personal_root / normalize_rel(rollback_info.get("target_rel") or item["target_rel"])
            restore_rel = normalize_rel(rollback_info.get("source_rel") or item["source_rel"])
            restore = self.personal_root / restore_rel
            if restore.exists():
                restore = restore.parent / f"rollback_{time.strftime('%Y%m%d')}_{restore.name}"
                restore_rel = self._rel(restore)
            if not target.exists() or not target.is_file():
                errors.append({"item_id": item["item_id"], "error": "target_missing"})
                continue
            if _sha256_file(target) != rollback_info.get("target_sha256"):
                errors.append({"item_id": item["item_id"], "error": "target_sha256_mismatch"})
                continue
            try:
                if item["operation"] == "copy":
                    target.unlink()
                else:
                    rollback_move(target, restore)
                self._mark_item_rolled_back(item["item_id"], restore_rel)
                restored.append({"item_id": item["item_id"], "restore_rel": restore_rel, "target_rel": self._rel(target), "status": "rolled_back"})
            except Exception as exc:
                errors.append({"item_id": item["item_id"], "error": f"{type(exc).__name__}:{exc}"})
        self._mark_plan_rolled_back(plan_id, bool(errors))
        manifest_path = write_rollback_manifest(self.report_root, plan_id, {"plan_id": plan_id, "rollback_items": restored, "errors": errors})
        return self._public(
            {
                "ok": not errors and bool(restored),
                "schema": "digua_auto_organizer_rollback_v1",
                "plan_id": plan_id,
                "rolled_back_count": len(restored),
                "error_count": len(errors),
                "items": restored,
                "errors": errors,
                "rollback_manifest": str(manifest_path.relative_to(self.report_root)),
                "rollback_verified": not errors and bool(restored),
                "raw_path_returned": False,
            }
        )

    def plan(self, plan_id: str) -> dict[str, Any]:
        return self._plan({"plan_id": plan_id})

    def recent(self, limit: int = 20) -> dict[str, Any]:
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            rows = [dict(row) for row in conn.execute("SELECT * FROM auto_organize_plans ORDER BY created_at DESC LIMIT ?", (int(limit),))]
        finally:
            conn.close()
        return self._public({"ok": True, "schema": "digua_auto_organizer_recent_v1", "plans": rows, "raw_path_returned": False})

    def _plan(self, payload: dict[str, Any], *, include_private: bool = False) -> dict[str, Any]:
        plan_id = str(payload.get("plan_id") or "")
        if not plan_id:
            return self._error("plan_id_required")
        migrate(self.db_path)
        conn = connect(self.db_path)
        try:
            plan_row = conn.execute("SELECT * FROM auto_organize_plans WHERE plan_id=?", (plan_id,)).fetchone()
            if plan_row is None:
                return self._error("plan_not_found")
            item_rows = [dict(row) for row in conn.execute("SELECT * FROM auto_organize_items WHERE plan_id=? ORDER BY created_at,item_id", (plan_id,))]
        finally:
            conn.close()
        items = []
        for row in item_rows:
            row["classification_basis"] = json.loads(row.pop("classification_basis_json") or "{}")
            row["naming_basis"] = json.loads(row.pop("naming_basis_json") or "{}")
            if not include_private:
                row.pop("rollback_json", None)
            items.append(self._decorate_public_item(row))
        return self._public({"ok": True, "schema": "digua_auto_organizer_plan_detail_v1", "plan": dict(plan_row), "items": items, "raw_path_returned": False})

    @staticmethod
    def _decorate_public_item(row: dict[str, Any]) -> dict[str, Any]:
        basis = row.get("classification_basis") if isinstance(row.get("classification_basis"), dict) else {}
        row.setdefault("category_zh", row.get("target_category_zh"))
        row.setdefault("ai_driven", bool(basis.get("ai_driven")) and basis.get("fallback_used") is not True)
        row.setdefault("resolution_source", basis.get("resolution_source") or basis.get("source"))
        row.setdefault("fallback_used", bool(basis.get("fallback_used")))
        row.setdefault("rollback_available", True)
        row.setdefault("raw_path_returned", False)
        return row

    @staticmethod
    def _recent_state(conn: Any) -> dict[str, Any]:
        state: dict[str, Any] = {
            "last_ai_driven_plan": None,
            "last_fallback_blocker": None,
            "last_rollback_status": None,
        }
        try:
            row = conn.execute(
                """
                SELECT p.plan_id,p.status,i.classification_basis_json,i.created_at
                FROM auto_organize_plans p
                LEFT JOIN auto_organize_items i ON i.plan_id=p.plan_id
                ORDER BY p.created_at DESC,i.created_at DESC
                LIMIT 1
                """
            ).fetchone()
        except Exception:
            return state
        if not row:
            return state
        basis = json.loads(row["classification_basis_json"] or "{}") if row["classification_basis_json"] else {}
        state["last_ai_driven_plan"] = {
            "plan_id": row["plan_id"],
            "status": row["status"],
            "ai_driven": bool(basis.get("ai_driven")) and basis.get("fallback_used") is not True,
            "resolution_source": basis.get("resolution_source") or basis.get("source"),
            "fallback_used": bool(basis.get("fallback_used")),
        }
        if basis.get("fallback_used"):
            state["last_fallback_blocker"] = {
                "blocker": basis.get("blocker") or "ai_index_missing_for_asset",
                "fallback_available": basis.get("fallback_available", True),
                "product_demo_allowed": basis.get("product_demo_allowed", False),
            }
        if row["status"] in {"rolled_back", "rollback_partial"}:
            state["last_rollback_status"] = {"plan_id": row["plan_id"], "status": row["status"]}
        return state

    def _pre_execute_error(self, source: Path, target: Path, item: dict[str, Any]) -> str | None:
        if not source.exists() or not source.is_file() or source.is_symlink():
            return "source_missing_or_not_regular_file"
        if not self._is_under_allowed_source(source):
            return "source_outside_allowed_roots"
        if not self._is_under_target_root(target):
            return "target_outside_allowed_root"
        if target.exists():
            return "target_exists_no_overwrite"
        if target.parent.is_symlink():
            return "target_parent_symlink"
        if _sha256_file(source) != item["source_sha256"]:
            return "source_sha256_mismatch"
        return None

    def _mark_item_executed(self, item_id: str, target_rel: str, rollback_payload: dict[str, Any]) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE auto_organize_items
                SET status='executed', target_rel=?, target_hash=?, final_filename=?, rollback_json=?, executed_at=?
                WHERE item_id=?
                """,
                (target_rel, path_hash(target_rel), Path(target_rel).name, json.dumps(rollback_payload, ensure_ascii=False, sort_keys=True), _now(), item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _mark_item_rolled_back(self, item_id: str, restore_rel: str) -> None:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT rollback_json FROM auto_organize_items WHERE item_id=?", (item_id,)).fetchone()
            rollback_payload = json.loads((row["rollback_json"] if row else None) or "{}")
            rollback_payload["restore_rel"] = restore_rel
            conn.execute(
                "UPDATE auto_organize_items SET status='rolled_back', rollback_json=? WHERE item_id=?",
                (json.dumps(rollback_payload, ensure_ascii=False, sort_keys=True), item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _mark_plan_executed(self, plan_id: str, partial: bool) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("UPDATE auto_organize_plans SET status=?, executed_at=? WHERE plan_id=?", ("partial" if partial else "executed", _now(), plan_id))
            conn.commit()
        finally:
            conn.close()

    def _mark_plan_rolled_back(self, plan_id: str, partial: bool) -> None:
        conn = connect(self.db_path)
        try:
            conn.execute("UPDATE auto_organize_plans SET status=?, rolled_back_at=? WHERE plan_id=?", ("rollback_partial" if partial else "rolled_back", _now(), plan_id))
            conn.commit()
        finally:
            conn.close()

    def _rel(self, path: Path) -> str:
        return normalize_rel(path.resolve(strict=False).relative_to(self.personal_root.resolve(strict=False)).as_posix())

    def _allowed_source_roots(self) -> set[str]:
        return {normalize_rel(str(item)) for item in self.flags.get("auto_organize_allowed_source_roots") or ["Uploads", "待整理"]}

    def _is_under_allowed_source(self, path: Path) -> bool:
        rel = self._rel(path)
        return any(rel == root or rel.startswith(root + "/") for root in self._allowed_source_roots())

    def _is_under_target_root(self, path: Path) -> bool:
        rel = self._rel(path)
        root = normalize_rel(str(self.flags.get("auto_organize_target_root") or "AI整理"))
        return rel == root or rel.startswith(root + "/")

    def _approval_phrase(self, plan_id: str) -> str:
        return f"APPROVE AUTO ORGANIZE {plan_id}"

    def _approval_token(self, plan_id: str) -> str:
        return hmac.new(DEFAULT_SECRET.encode("utf-8"), plan_id.encode("utf-8"), hashlib.sha256).hexdigest()

    def _error(self, error: str) -> dict[str, Any]:
        return {"ok": False, "error": error, "raw_path_returned": False, "qwen_execution_authority": False}

    def _public(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload, ensure_ascii=False)
        payload["raw_path_returned"] = any(marker in encoded for marker in RAW_PATH_MARKERS)
        payload.setdefault("qwen_execution_authority", False)
        payload.setdefault("cloud_private_raw_egress", False)
        return payload


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
