# 040 Test Results

- Windows PATH lacks node/npm, so node --check and fresh Playwright CLI could not run in this audit.
- Tracked Python compile has one historical Dream7B probe IndentationError in scripts/probes/dream7b_gguf_param_matrix_probe.py.
- `py -3 -m pytest tests` passed 82 tests during this audit.

| command | exit | pass | missing_executable |
| --- | --- | --- | --- |
| node --check web/static/digua_ai_nas_v2.js | 127 | False | True |
| py -3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py | 0 | True | False |
| py -3 -c import subprocess, py_compile, sys; raw=subprocess.check_output(['git','ls-files','*.py']); files=raw.decode('utf-8','replace').splitlines(); failed=[]<br>for f in files:<br>    try: py_compile.compile(f, doraise=True)<br>    except Exception as e: failed.append((f, str(e)))<br>print('tracked_py_files', len(files)); print('failed', len(failed))<br>for path, err in failed[:80]: print(path + ': ' + err.replace('\n',' | ')[:500])<br>sys.exit(1 if failed else 0) | 1 | False | False |
| py -3 -m pytest tests | 0 | True | False |
| py -3 SELF_CHECK.py | 0 | True | False |
