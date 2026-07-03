#!/usr/bin/env python3
"""Summarize final segment scale sweep outputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from common_metrics import tensor_stats, logits_compare, write_json


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sweep-dir', required=True, help='Directory containing <case>/<variant>/logits.npy')
    ap.add_argument('--reference-dir', default=None, help='Optional directory containing <case>/last_token_logits.npy')
    ap.add_argument('--out-json', required=True)
    args=ap.parse_args()
    base=Path(args.sweep_dir)
    refbase=Path(args.reference_dir) if args.reference_dir else None
    out={'cases': []}
    for case_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
        centry={'case_id': case_dir.name, 'variants': []}
        ref=None
        if refbase and (refbase/case_dir.name/'last_token_logits.npy').exists():
            ref=np.load(refbase/case_dir.name/'last_token_logits.npy')
        for vdir in sorted([p for p in case_dir.iterdir() if p.is_dir()]):
            logit_path=vdir/'logits.npy'
            if not logit_path.exists():
                continue
            arr=np.load(logit_path)
            v={'variant': vdir.name, 'stats': tensor_stats(arr)}
            if ref is not None:
                v['compare_to_ref']=logits_compare(ref, arr)
            centry['variants'].append(v)
        out['cases'].append(centry)
    write_json(args.out_json, out)

if __name__ == '__main__':
    main()
