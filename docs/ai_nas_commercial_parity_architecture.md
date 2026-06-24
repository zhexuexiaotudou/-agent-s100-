# AI-NAS Commercial NAS Parity Architecture

Date: 2026-06-23

## Decision Boundary

The current system has passed the ten-goal S100P closure gate:

- `tmp/ai_nas_ten_goal_s100p_closure/ten_goal_s100p_closure_gate_latest.json`
- verdict: `ok_ai_nas_ten_goal_s100p_closure_gate`
- goals ok: `10/10`
- active text model: `Qwen2.5-1.5B-Instruct-S100P-official`
- active profile: `cache_len_512_chunk_128_q8`

This is enough to call the project an AI-NAS intelligence layer and demo-ready
appliance route on top of an existing NAS backend. It is not enough to call it
a full commercial NAS replacement. Commercial parity must be gated separately
because top NAS products include disk, protocol, account, sync, mobile, and
long-running operational surfaces that are outside the current closure gate.

## Architecture Split

| Capability | Current evidence/status | Project-owned implementation | NAS-delegated capability | Explicit non-goal for current release | Future plugin/adapter | Required acceptance gate |
| --- | --- | --- | --- | --- | --- | --- |
| Storage namespace and file inventory | Goal 1 passed through `ok_nas_storage_foundation_gate`; 10,000-file local fixture validated | AI-NAS indexing, metadata cache, safe report generation, operator-visible evidence paths | Durable storage, volume layout, filesystem repair, low-level quota enforcement | Replacing the NAS storage engine | Storage inventory adapter for each NAS vendor | `ai_nas_storage_backend_contract_gate`: verifies read/list/stat behavior against a real mounted NAS share and confirms no destructive writes during inventory |
| RAID and storage pool management | Not covered by ten-goal gate | Read-only display of NAS-reported pool health and risk labels | RAID creation, rebuild, scrub, spare management, pool expansion, volume encryption | Implementing RAID or replacing vendor storage pool tools | Vendor RAID-status adapter | `ai_nas_raid_status_readonly_gate`: reads real NAS pool status, detects degraded/healthy/sample states, and proves AI cannot mutate pool configuration |
| Disk health and SMART | Goal 8 includes local disk monitoring, not vendor-complete SMART parity | Normalize disk health, temperature, capacity, and warning evidence into reports | SMART collection, disk firmware tools, bad-block repair, disk replacement workflow | Claiming full disk-health parity | SMART/udev/vendor API adapter | `ai_nas_disk_health_contract_gate`: captures disk health from live NAS APIs or host tools and maps every warning to source evidence |
| Snapshots, trash, and versions | Goal 3 passed with local trash/version/snapshot behavior | AI-visible recovery catalog, snapshot browsing summaries, operator-confirmed restore requests | Real filesystem snapshots, retention policy enforcement, immutable snapshot protection | Replacing Btrfs/ZFS/vendor snapshot engines | Snapshot catalog adapter | `ai_nas_real_snapshot_mapping_gate`: maps real snapshot IDs to AI-NAS entries and verifies restore preview before any restore action |
| Backup and restore | Goal 4 passed with local backup/sync fixture | Backup task metadata, evidence reports, restore preview, non-destructive audit | Vendor backup engines, cloud backup credentials, dedupe, encryption, retention enforcement | Claiming production backup completeness | Backup task adapter and restore-preview adapter | `ai_nas_backup_restore_contract_gate`: verifies backup run evidence, restore dry-run, retention metadata, and explicit approval before restore |
| SMB and NFS | Goal 9 records protocol adapter stubs only | Adapter registry, route metadata, read-only capability display, AI planning | Production SMB/NFS daemons, ACL enforcement, locking, oplocks, Kerberos/AD | Shipping protocol daemons | SMB/NFS status adapters | `ai_nas_protocol_adapter_contract_gate`: proves protocol shares are detected and mapped to AI-NAS scope without bypassing NAS ACLs |
| WebDAV | Goal 9 records WebDAV adapter stub | WebDAV route metadata and operator UI hooks | WebDAV server, TLS, account auth, external publishing controls | Running a public WebDAV endpoint | WebDAV status and link adapter | `ai_nas_webdav_contract_gate`: confirms URLs, auth mode, and scope mapping without exposing unauthorized paths |
| Mobile sync and photo backup | Not covered as vendor parity | AI photo search, album metadata, duplicate/similar suggestions | Mobile apps, background upload, conflict resolution, device trust, push notifications | Replacing Synology/QNAP/mobile app ecosystems | Mobile-upload event adapter | `ai_nas_mobile_sync_observer_gate`: observes uploaded files and conflicts from vendor sync logs without claiming app replacement |
| User ACL inheritance | Goal 2 passed for local AI-NAS users/groups/ACLs | Identity cache, route-level permission checks, AI retrieval filters | POSIX ACLs, SMB ACLs, AD/LDAP groups, inherited permissions from real NAS shares | Claiming permission-complete NAS parity | Real ACL mapping adapter | `ai_nas_real_acl_mapping_gate`: verifies per-user list/search/summary results against real NAS ACLs and inherited groups |
| Web NAS OS portal | Goal 5 passed with file, media, backup, user, ops, audit, and AI entries | Operator portal, module links, report visibility, demo workflows | Vendor admin console, full settings surface, package center, app store | Replacing the vendor UI | Portal plugin registry | `ai_nas_operator_portal_parity_gate`: validates navigation, module health, report links, and clear delegation labels |
| AI Copilot and document knowledge base | Goal 7 passed; Qwen2.5 S100P acceptance passed | Grounded file retrieval, folder Q&A, report generation, citations, refusal policy | None except storage and ACL source of truth | Unbounded general chatbot claims | Tool-call expansion plugins | `ai_nas_conversation_grounding_gate`: verifies multi-turn answers are grounded, cited, scoped, and ACL-filtered |
| Image, video, OCR | Official vision route demo-ready; YOLO image/video verified; LLM-caption-first search gate added; OCR wrapper pending in vision route doc | Visual route selection, structured caption index, evidence packets, local embedding fallback, privacy policy | Camera/mobile upload, vendor media transcoding | Production person/photo semantics until caption and privacy gates pass | Vision-caption/OCR/video worker plugins | `ai_nas_multimodal_semantics_gate`: verifies caption search, OCR, frame indexing, and privacy filters separately |
| App ecosystem | Goal 9 passed for plugin/protocol registry | Plugin manifest, lifecycle status, adapter records, UI integration | Container runtime, package signing, app store distribution | Replacing Docker/package center | Signed plugin adapter | `ai_nas_plugin_lifecycle_gate`: install/start/stop/uninstall with audit and permission manifests |
| Updates and rollback | Not covered as commercial product parity | Versioned config/report migrations, rollback instructions, gate history | OS update engine, bootloader rollback, kernel/driver rollback | Claiming appliance OTA parity | Release bundle adapter | `ai_nas_update_rollback_gate`: verifies staged update, migration dry-run, rollback path, and previous gate preservation |

## First Commercial-Parity Milestone

The next milestone should not be "replace a top NAS." It should be:

> AI-NAS runs as an ACL-aware, evidence-grounded intelligence layer over a real
> NAS share while delegating RAID, disk, protocol, mobile, and low-level storage
> controls to the NAS.

This milestone is acceptable only when the following gates pass on live NAS
inputs, not only local fixtures:

- `ai_nas_real_acl_mapping_gate`
- `ai_nas_storage_backend_contract_gate`
- `ai_nas_real_snapshot_mapping_gate`
- `ai_nas_backup_restore_contract_gate`
- `ai_nas_protocol_adapter_contract_gate`
- `ai_nas_operator_portal_parity_gate`

## Implementation Rule

Every commercial NAS feature must be tagged as one of four classes before code
is written:

- `owned`: AI-NAS implements and gates the behavior.
- `delegated`: the existing NAS remains source of truth and AI-NAS only reads,
  links, or requests approved actions.
- `adapter`: AI-NAS needs a vendor/protocol plugin before it can make claims.
- `non_goal`: out of current release scope and must not appear as a product
  claim.

If a feature does not have one of these tags, it is not ready for DeepSeek-class
mechanical implementation.
