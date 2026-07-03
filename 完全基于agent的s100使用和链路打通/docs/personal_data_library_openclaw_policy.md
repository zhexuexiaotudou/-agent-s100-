# Personal Data Library Policy for OpenClaw

## Purpose

`Personal` is treated as the user's personal data library on the NAS. OpenClaw is allowed to organize this library only through bounded, auditable operations.

## Safety Model

The default mode is non-destructive:

- do not delete original files;
- do not move original files;
- do not rename original files;
- do not overwrite source files;
- copy organized views into `Personal/Sorted`;
- report SHA256 duplicate groups, but do not remove duplicates automatically;
- write Markdown and JSON reports under `/mnt/nas/openclaw/reports/personal-data-sort`.

This follows the safer NAS pattern: AI can index, classify, tag, and suggest organization; destructive actions such as move, delete, overwrite, or duplicate removal require a separate explicit human-approved workflow.

## Current OpenClaw Tool

Allowlisted tool:

```text
personal_data_sort_probe
personal_data_sort_dry_run_probe
```

Recommended preview command for recording:

```bash
bash scripts/run_allowlisted_tool.sh personal_data_sort_dry_run_probe Personal Movies Sorted /mnt/nas/openclaw/reports/personal-data-sort-dry-run
```

This writes a Markdown/JSON plan only and skips SMB upload.

Explicit apply/copy command:

```bash
bash scripts/run_allowlisted_tool.sh personal_data_sort_probe Personal / Sorted /mnt/nas/openclaw/reports/personal-data-sort
```

OpenClaw prompt:

```text
请调用 s100p_run_probe，tool_id=personal_data_sort_probe，参数为：Personal / Sorted /mnt/nas/openclaw/reports/personal-data-sort。整理 Personal 文件夹里的内容，复制分类到 Sorted，保留原文件，不删除原文件。
```

## Approved Scope

The tool only accepts the `Personal` SMB share and these source scopes:

- `/`
- `Movies`
- `Documents`
- `Photos`
- `Datasets`
- `Inbox`

The output root is restricted to:

```text
Personal/Sorted
```

The tool skips recycle, snapshot, and previous sorted-output folders:

- `@Recycle`
- `@Recently-Snapshot`
- `.snapshot`
- `#recycle`
- `Sorted`

## Current Verification

The latest verified run sorted the `Personal` movie examples into:

```text
Personal/Sorted/Movies/
```

with genre subfolders such as:

- `Action`
- `Animation`
- `Comedy`
- `Crime`
- `Documentary`
- `Drama`
- `Musical`
- `Mystery`
- `Sci-Fi`
- `Thriller`

Latest report path:

```text
/mnt/nas/openclaw/reports/personal-data-sort/personal_data_sort_20260611-131858/personal_data_sort.md
```

## Not Yet Enabled

These actions remain intentionally disabled:

- move source files into final locations;
- delete duplicates;
- overwrite existing source files;
- permanent cleanup;
- full-disk destructive organization.

Before any destructive mode is considered, the NAS share should have recycle bin and snapshot protection enabled and the action should produce a preview report first.
