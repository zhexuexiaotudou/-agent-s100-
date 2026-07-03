# AI NAS Movie Sort Demo Runbook

## Purpose

Demonstrate an AI NAS style workflow where OpenClaw running on S100P organizes movie-like files by type on NAS.

This demo is intentionally bounded. It uses sample movie placeholder files and deterministic filename/metadata classification rules so the recording can show the NAS workflow without touching a real media library.

## Scope

In scope:

- Create or reuse a demo inbox under `/mnt/nas/openclaw/demo/ai-nas-movie-sort/inbox`.
- Classify movie-like demo files by type.
- Copy files into `/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/<type>/`.
- Write Markdown and JSON evidence under `/mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort`.

Out of scope:

- Real movie library mutation.
- File deletion.
- External API calls.
- Persistent model server startup.
- Robot capability.
- ROS2.
- rosbag.

## Command

Run on S100P from the repository checkout:

```bash
scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe
```

Optional explicit paths:

```bash
scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe \
  /mnt/nas/openclaw/demo/ai-nas-movie-sort \
  /mnt/nas/openclaw/reports/teacher-demos/ai-nas-movie-sort
```

## Output

The probe prints the generated Markdown report path. The report directory contains:

```text
movie_sort_demo.md
movie_sort_demo.json
```

The demo library is written under:

```text
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/
```

Each type directory contains copied sample files and:

```text
MANIFEST.md
<file>.movie.json
```

## Recording Steps

1. Show the NAS demo inbox:

```text
/mnt/nas/openclaw/demo/ai-nas-movie-sort/inbox
```

2. Ask OpenClaw to execute:

```bash
scripts/run_allowlisted_tool.sh ai_nas_movie_sort_demo_probe
```

3. Show the generated type directories under:

```text
/mnt/nas/openclaw/demo/ai-nas-movie-sort/library/
```

4. Open `movie_sort_demo.md` from the generated report directory.
5. Show `processed_file_count`, `types`, and `Sorted Records`.
6. Show that originals remain in `inbox/`.

## Acceptance

- `movie_sort_demo.json` contains `verdict: ok_ai_nas_movie_sort_demo_probe`.
- `movie_sort_demo.json` contains `classification_engine: deterministic_filename_metadata_rules`.
- `movie_sort_demo.json` contains `originals_preserved: true`.
- `movie_sort_demo.json` contains `scope.real_media_library_touched: false`.
- Type directories are created under `library/`.
- All writes stay inside the approved demo root and report root.

## Classification Rules

The classifier is implemented in:

```text
scripts/probes/ai_nas_movie_sort_demo_probe.sh
```

Current output types:

```text
Sci-Fi
Animation
Documentary
Thriller
Action
Comedy
Drama
Unclassified
```
