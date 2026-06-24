# Teacher Demo Real Run - 2026-06-09 13:12 CST

## Run Context

- Local working directory: `F:\Project\Digua`
- Repository directory: `F:\Project\Digua\完全基于agent的s100使用和链路打通`
- Remote script deployment root: `/mnt/nas/openclaw/demo-runner/teacher-demo-scripts`
- Execution host: S100P SSH target from `F:\Project\Digua\scripts\startup_link_check\link-check.config.json`
- Execution method: SSH ran the same allowlisted commands that the OpenClaw recording runbook asks OpenClaw to trigger.

## Commands Run

```bash
cd /mnt/nas/openclaw/demo-runner/teacher-demo-scripts
bash scripts/run_allowlisted_tool.sh openclaw_entry_demo_probe
bash scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe
```

## OpenClaw Entry Demo Result

- Report: `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry/openclaw_entry_demo_20260609-131232/openclaw_entry_demo.md`
- JSON: `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry/openclaw_entry_demo_20260609-131232/openclaw_entry_demo.json`
- Verdict in report: `ok_openclaw_entry_demo_probe`
- NAS mounted in report: `True`
- NAS writable in report: `True`
- OpenClaw status probe status in report: `ok`
- OpenClaw status probe report: `/mnt/nas/openclaw/logs/probes/openclaw_status_20260609-131232.txt`
- Root user service active capture: `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry/openclaw_entry_demo_20260609-131232/captures/openclaw_gateway_root_active.txt`
- Root user service active value: `active`
- Port capture: `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry/openclaw_entry_demo_20260609-131232/captures/port_18789.txt`
- Port capture values:

```text
LISTEN 0      511        127.0.0.1:18789      0.0.0.0:*
LISTEN 0      511            [::1]:18789         [::]:*
```

- NAS findmnt capture: `/mnt/nas/openclaw/reports/teacher-demos/openclaw-entry/openclaw_entry_demo_20260609-131232/captures/nas_findmnt.txt`
- NAS NFS source value observed: `169.254.143.37:/OpenClawWorkspace`

## AI NAS Movie Sort Demo Result

- Report: `/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort/movie_sort_demo_20260609-131233/movie_sort_demo.md`
- JSON: `/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort/movie_sort_demo_20260609-131233/movie_sort_demo.json`
- Verdict in report: `ok_ai_nas_movie_sort_demo_probe`
- Demo root: `/mnt/nas/openclaw/demo/ai-nas-movie-sort`
- Inbox: `/mnt/nas/openclaw/demo/ai-nas-movie-sort/inbox`
- Library: `/mnt/nas/openclaw/demo/ai-nas-movie-sort/library`
- Classification engine: `deterministic_filename_metadata_rules`
- Processed file count: `6`
- Types: `Animation, Documentary, Sci-Fi, Thriller, Unclassified`

Sorted records from the generated report:

```text
Family.Home.Video.2026.Unclassified.movie.txt -> Unclassified
Inception.2010.Thriller.movie.txt -> Thriller
Interstellar.2014.Sci-Fi.movie.txt -> Sci-Fi
Planet.Earth.2006.Documentary.movie.txt -> Documentary
The.Matrix.1999.Sci-Fi.movie.txt -> Sci-Fi
Toy.Story.1995.Animation.movie.txt -> Animation
```

Generated library files observed:

```text
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Animation/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Animation/Toy.Story.1995.Animation.movie.txt
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Documentary/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Documentary/Planet.Earth.2006.Documentary.movie.txt
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Sci-Fi/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Sci-Fi/Interstellar.2014.Sci-Fi.movie.txt
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Sci-Fi/The.Matrix.1999.Sci-Fi.movie.txt
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Thriller/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Thriller/Inception.2010.Thriller.movie.txt
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Unclassified/MANIFEST.md
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/Unclassified/Family.Home.Video.2026.Unclassified.movie.txt
```

## Review

- The OpenClaw entry demo has current evidence that the gateway is active as the root user service on S100P, port `18789` is listening on loopback, and persistence is under the NAS NFS mount.
- The AI NAS demo has current evidence that S100P-side execution creates typed movie folders and reports under NAS paths.
- This SSH run validates the runnable path. For the teacher video, run the same two allowlisted commands through the OpenClaw entry so the recording shows OpenClaw initiating the task.
