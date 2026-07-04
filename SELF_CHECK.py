#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

required = [
    'src/harness/token_budget_integration.py',
    'reports/17000_tokenizer_product_baseline_lock.json',
    'reports/17010_qwen_tokenizer_identity_gate.json',
    'reports/17020_privacy_redactor_product_gate.json',
    'reports/17030_context_compressor_product_gate.json',
    'reports/17040_cloud_route_decider_product_gate.json',
    'reports/17050_token_trace_harness_integration_gate.json',
    'reports/17060_openclaw_token_budget_product_api_gate.json',
    'reports/17070_token_budget_benchmark_results.json',
    'reports/17080_token_cost_reduction_analysis.json',
    'reports/17090_token_budget_product_integration_gate.json',
    'reports/17100_token_budget_product_regression_gate.json',
    'reports/17110_updated_claim_matrix_token_budget_gate.json',
]
missing = [item for item in required if not Path(item).exists()]
summary = json.loads(Path('reports/17070_token_budget_benchmark_results.json').read_text(encoding='utf-8'))
analysis = json.loads(Path('reports/17080_token_cost_reduction_analysis.json').read_text(encoding='utf-8'))
checks = {
    'missing_required_count': len(missing),
    'real_qwen_tokenizer_used': summary.get('real_qwen_tokenizer_used'),
    'private_leak_count': summary.get('private_leak_count'),
    'total_cases': summary.get('total_cases'),
    'quality_pass_rate': summary.get('quality_pass_rate'),
    'final_verdict': analysis.get('final_verdict'),
}
print(json.dumps({'ok': len(missing) == 0 and checks['real_qwen_tokenizer_used'] and checks['private_leak_count'] == 0 and checks['total_cases'] >= 120 and checks['quality_pass_rate'] >= 0.9, 'missing': missing, 'checks': checks}, ensure_ascii=False, indent=2))
