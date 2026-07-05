param([Parameter(Mandatory=$true)][string]$ModelDir,[string]$OutDir='semantic_truth_output')
py -3 .\export_semantic_truth.py --model-dir $ModelDir --cases-jsonl .\semantic_cases.jsonl --output-root $OutDir --dtype bfloat16 --device auto --fallback-fp32
