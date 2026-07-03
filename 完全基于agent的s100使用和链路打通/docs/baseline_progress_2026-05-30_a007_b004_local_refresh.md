# Baseline Progress: A-007/B-004 Local Refresh

Date: 2026-05-30

The active audit lane is `continue-non-nas-readonly-only`, so this pass only
refreshed local browser automation evidence and inventoried existing robot
dataset cards. It did not depend on NAS, record ROS bags, change services, or
call control APIs.

## Implementation

`refresh-baseline-local-readonly` now runs:

```text
browser_smoke_probe /root/.openclaw/workspace/reports/browser-smoke
dataset_card_inventory_probe /root/.openclaw/workspace/robot_datasets /root/.openclaw/workspace/reports/robot-datasets
```

`dataset_card_inventory_probe` is read-only: it scans existing
`DATASET_CARD.md` files, counts bag and metadata files beside each card, and
writes a Markdown/JSON inventory. It never starts `rosbag`, creates datasets,
or modifies the dataset directories.

## Latest Evidence

```text
browser smoke: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260530-171336.md
browser verdict: ok
browser screenshot: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260530-171336.png
dataset inventory: /root/.openclaw/workspace/reports/robot-datasets/dataset_card_inventory_20260530-171340.md
dataset card count: 4
latest dataset card: /root/.openclaw/workspace/robot_datasets/rosbag_session_20260527-052005/DATASET_CARD.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-171354.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-171354.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-171355.md
```

## Tracking Impact

A-007 now points at same-round local browser evidence with a captured PNG and
valid PNG magic. B-004 now has both the latest existing dataset card and a
same-round read-only inventory of all existing cards.

This does not complete A-009. A real operator-approved named capture is still
required before the ROS bag capture baseline is accepted.
