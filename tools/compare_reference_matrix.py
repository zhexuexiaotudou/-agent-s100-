#!/usr/bin/env python3
"""Compare logits rows across HF/GGUF/S100P references.

This scaffold expects directories like:
  evidence/reference_matrix/<row>/<case_id>/last_token_logits.npy
Rows may include hf_bf16, gguf_f16, gguf_q4_0, gguf_q4_k_m, s100p_bpu.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from common_metrics import logits_compare, tensor_stats, write_json

ROWS = ['hf_bf16', 'gguf_f16', 'gguf_q4_0', 'gguf_q4_k_m', 's100p_bpu']


def load_case_ids(cases_jsonl: Path):
    ids=[]
    for line in cases_jsonl.read_text(encoding='utf-8').splitlines():
        if line.strip():
            ids.append(json.loads(line)['case_id'])
    return ids


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--matrix-dir', required=True)
    ap.add_argument('--cases-jsonl', required=True)
    ap.add_argument('--out-json', required=True)
    args=ap.parse_args()
    base=Path(args.matrix_dir)
    out={'rows': {}, 'cases': []}
    case_ids=load_case_ids(Path(args.cases_jsonl))
    for row in ROWS:
        out['rows'][row]={'available_cases': []}
        for cid in case_ids:
            p=base/row/cid/'last_token_logits.npy'
            if p.exists(): out['rows'][row]['available_cases'].append(cid)
    for cid in case_ids:
        entry={'case_id': cid, 'available': {}, 'stats': {}, 'comparisons': {}}
        arrays={}
        for row in ROWS:
            p=base/row/cid/'last_token_logits.npy'
            entry['available'][row]=p.exists()
            if p.exists():
                arr=np.load(p)
                arrays[row]=arr
                entry['stats'][row]=tensor_stats(arr)
        ref='hf_bf16' if 'hf_bf16' in arrays else ('gguf_f16' if 'gguf_f16' in arrays else None)
        if ref:
            for row, arr in arrays.items():
                if row != ref:
                    entry['comparisons'][f'{ref}_vs_{row}']=logits_compare(arrays[ref], arr)
        if 'gguf_q4_k_m' in arrays and 's100p_bpu' in arrays:
            entry['comparisons']['gguf_q4_k_m_vs_s100p_bpu']=logits_compare(arrays['gguf_q4_k_m'], arrays['s100p_bpu'])
        out['cases'].append(entry)
    write_json(args.out_json, out)

if __name__ == '__main__':
    main()
