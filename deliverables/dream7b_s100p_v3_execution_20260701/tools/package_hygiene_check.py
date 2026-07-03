#!/usr/bin/env python3
"""Repo/package hygiene checker for v3 evidence."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from common_artifact_utils import sha256_file, utc_now_iso, write_json


def check_json_files(root: Path) -> List[Dict[str, Any]]:
    out = []
    for p in sorted(root.glob('reports/**/*.json')) + sorted(root.glob('01_final_evidence/**/*.json')):
        try:
            json.loads(p.read_text(encoding='utf-8'))
            out.append({'path': str(p), 'parseable': True})
        except Exception as e:
            out.append({'path': str(p), 'parseable': False, 'exception': f'{type(e).__name__}: {e}'})
    return out


def git_status(root: Path) -> Dict[str, Any]:
    if not (root / '.git').exists():
        return {'is_git_repo': False}
    def run(cmd):
        return subprocess.run(cmd, cwd=root, text=True, capture_output=True).stdout.strip()
    return {'is_git_repo': True, 'commit': run(['git','rev-parse','HEAD']), 'status_short': run(['git','status','--short'])}


def check_zip_paths(zip_path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    bad = [n for n in names if '\\' in n]
    return {'zip_path': str(zip_path), 'file_count': len(names), 'names_with_backslash': bad[:20], 'bad_count': len(bad)}


def raw_subset_status(root: Path) -> Dict[str, Any]:
    manifest = root / 'RAW_EVIDENCE_SUBSET_MANIFEST.json'
    raw_root = root / 'raw_evidence_subset'
    if not manifest.exists() and not raw_root.exists():
        return {'status': 'unknown', 'manifest_exists': False, 'file_count': 0}
    files = list(raw_root.rglob('*.npy')) if raw_root.exists() else []
    if not manifest.exists():
        return {'status': 'partial', 'manifest_exists': False, 'file_count': len(files)}
    try:
        obj = json.loads(manifest.read_text(encoding='utf-8'))
        count = int(obj.get('file_count', len(obj.get('files', []))))
    except Exception as exc:
        return {'status': 'fail', 'manifest_exists': True, 'exception': f'{type(exc).__name__}: {exc}', 'file_count': len(files)}
    if count and files:
        return {'status': 'pass', 'manifest_exists': True, 'file_count': count, 'npy_file_count': len(files)}
    if count or files:
        return {'status': 'partial', 'manifest_exists': True, 'file_count': count, 'npy_file_count': len(files)}
    return {'status': 'fail', 'manifest_exists': True, 'file_count': count, 'npy_file_count': len(files)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--zip', default=None, help='Optional zip to inspect for POSIX paths')
    ap.add_argument('--output-json', default='reports/105_package_hygiene_v3.json')
    ap.add_argument('--output-md', default='reports/105_package_hygiene_v3.md')
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    json_checks = check_json_files(root)
    zip_check = check_zip_paths(Path(args.zip)) if args.zip else None
    parse_failures = [x for x in json_checks if not x['parseable']]
    zip_bad = bool(zip_check and zip_check['bad_count'])
    raw_status = raw_subset_status(root)
    verdict = 'pass' if not parse_failures and not zip_bad and raw_status['status'] in ('pass', 'unknown') else 'fail'
    report = {
        'schema_version': 'dream7b_s100p_package_hygiene_v3',
        'created_at_utc': utc_now_iso(),
        'package_hygiene_valid': verdict,
        'repo_root': str(root),
        'git': git_status(root),
        'json_parse_checks': json_checks,
        'zip_path_check': zip_check,
        'posix_paths_required': True,
        'raw_evidence_subset_available': raw_status['status'],
        'raw_evidence_subset_check': raw_status,
    }
    write_json(args.output_json, report)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(f'# Package hygiene v3\n\n- package_hygiene_valid: `{verdict}`\n- json_parse_failures: {len(parse_failures)}\n- zip_bad_paths: {zip_bad}\n', encoding='utf-8')

if __name__ == '__main__':
    main()
