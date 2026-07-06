# NAS Mount Guide

Supported modes:

- `nfs`: recommended for a dedicated OpenClaw workspace share.
- `smb`/`cifs`: supported with a credential file; passwords must not be logged.
- `local`: development and clean-install simulation mode.

The allowed production mount root is `/mnt/nas/openclaw`. Personal user data
must stay under `/mnt/nas/openclaw/Personal`, and OpenClaw must not be granted
access to the entire NAS.

