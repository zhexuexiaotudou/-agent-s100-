# systemd templates

Canonical deployable units live under `release/systemd/`. The installer renders
their `@DIGUA_*@` placeholders and keeps `digua-product-remote-ingress.service`
disabled until an administrator explicitly configures a remote adapter.
