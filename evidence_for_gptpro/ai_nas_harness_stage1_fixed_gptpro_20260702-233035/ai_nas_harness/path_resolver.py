from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _has_repo_markers(path: Path) -> bool:
    return (path / "config" / "workspace_registry.yaml").exists() and (path / "ai_nas_harness").exists()


def find_repo_root(start: str | Path | None = None) -> Path:
    env_root = os.environ.get("AI_NAS_REPO_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root))
    if start:
        candidates.append(Path(start))
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve().parents[1])
    for candidate in candidates:
        current = candidate.resolve()
        if current.is_file():
            current = current.parent
        for parent in [current, *current.parents]:
            if _has_repo_markers(parent):
                return parent
    return Path(__file__).resolve().parents[1]


def find_production_context_root(repo_root: str | Path | None = None, explicit: str | Path | None = None) -> Path:
    env_root = os.environ.get("AI_NAS_PRODUCTION_CONTEXT_ROOT")
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if env_root:
        candidates.append(Path(env_root))
    root = Path(repo_root) if repo_root else find_repo_root()
    candidates.extend([root / "production_context", root])
    for candidate in candidates:
        if (candidate / "scripts" / "probes" / "ai_nas_allowlisted_tool.sh").exists() or (
            candidate / "configs" / "systemd" / "openclaw-gateway.service"
        ).exists():
            return candidate.resolve()
    return (root / "production_context").resolve()


def resolve_asset(
    relative_path: str,
    *,
    repo_root: str | Path | None = None,
    production_context_root: str | Path | None = None,
    alternatives: Iterable[str] = (),
    required: bool = True,
) -> Path:
    root = find_repo_root(repo_root)
    prod_root = find_production_context_root(root, production_context_root)
    relative_candidates = [relative_path, *alternatives]
    roots = [root, prod_root]
    if prod_root.name == "production_context":
        roots.append(prod_root.parent)
    for base in roots:
        for rel in relative_candidates:
            path = (base / rel).resolve()
            if path.exists():
                return path
    if required:
        searched = [str((base / rel).resolve()) for base in roots for rel in relative_candidates]
        raise FileNotFoundError(f"required asset missing: {relative_path}; searched={searched}")
    return (root / relative_path).resolve()


def critical_asset_map(repo_root: str | Path | None = None, production_context_root: str | Path | None = None) -> dict[str, Path]:
    return {
        "dispatcher": resolve_asset(
            "scripts/probes/ai_nas_allowlisted_tool.sh",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/scripts/probes/ai_nas_allowlisted_tool.sh"],
        ),
        "qwen_gateway": resolve_asset(
            "scripts/qwen25_openai_gateway.py",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/scripts/qwen25_openai_gateway.py"],
        ),
        "openclaw_service": resolve_asset(
            "configs/systemd/openclaw-gateway.service",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/configs/systemd/openclaw-gateway.service"],
        ),
        "qwen_service": resolve_asset(
            "configs/systemd/qwen25-local-openai-gateway.service",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/configs/systemd/qwen25-local-openai-gateway.service"],
        ),
        "qwen_policy": resolve_asset(
            "configs/qwen25_official_route_policy.json",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/configs/qwen25_official_route_policy.json"],
        ),
        "dream7b_service": resolve_asset(
            "configs/systemd/dream7b-local-openai-gateway.service",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/configs/systemd/dream7b-local-openai-gateway.service"],
        ),
        "dream7b_18889_service": resolve_asset(
            "configs/systemd/dream7b-bpu-experimental-gateway-18889.service",
            repo_root=repo_root,
            production_context_root=production_context_root,
            alternatives=["production_context/configs/systemd/dream7b-bpu-experimental-gateway-18889.service"],
        ),
    }
