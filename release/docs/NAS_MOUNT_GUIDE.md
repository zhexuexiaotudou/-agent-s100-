# NAS Mount Guide

Use a dedicated share such as `/OpenClawWorkspace` mounted at
`/mnt/nas/openclaw`. Do not grant OpenClaw access to the entire NAS. NFS,
SMB/CIFS, and local directory mode are supported by the dry-run planner.

The discovery helper can normally infer a NAS candidate and supported
protocol, but it cannot infer the owner's intended authorization scope. The
user must always confirm the dedicated export/share. SMB credentials must use a
dedicated low-privilege account and a `0600`/`0400` credentials file. NFS must
allow the S100P client identity without granting the application the NAS root.

Information that remains user-supplied when it cannot be discovered:

- NAS IP/hostname;
- enabled NFS or SMB protocol;
- dedicated export/share name;
- SMB credentials file, or NAS-side NFS client authorization;
- explicit confirmation that this share is the complete AI-NAS access scope.
