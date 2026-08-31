# Local runtime blocker evidence

- Checked at: `2026-08-31T20:15:12.9711232+08:00`
- Host scope: current local Windows development host
- Secrets or personal identifiers captured: `NO`

## Container and database runtime inventory

Read-only command/path checks returned:

| Capability                  | Result                                       |
| --------------------------- | -------------------------------------------- |
| Docker CLI / Docker Desktop | `NOT INSTALLED / NOT FOUND`                  |
| Podman                      | `NOT INSTALLED / NOT FOUND`                  |
| nerdctl                     | `NOT INSTALLED / NOT FOUND`                  |
| WSL executable              | `PRESENT`                                    |
| Usable WSL distribution     | `NONE` — Lxss registry absent; list exit `1` |
| Local PostgreSQL/psql       | `NOT INSTALLED / NOT FOUND`                  |
| WinHTTP proxy               | `DIRECT ACCESS`                              |
| Chrome                      | `PRESENT`                                    |

No Logto/PostgreSQL process, container, application, API resource, test account or secret was created. The absence of a usable Linux container runtime blocks `docker compose config`, image pull, empty-volume initialization, persistence restart and every live protocol/browser test.

## Authority boundary

Installing Docker Desktop, enabling WSL2/virtualization or rebooting Windows is a system-level change outside the implicit repository-edit scope. The verification Slice therefore stops and requests explicit project-owner direction: either install/authorize a local Linux Docker + Compose runtime or provide an approved isolated Linux Docker host.

Even after a runtime is available, the project owner must provide or perform the separate fixed-broadband and mobile/hotspot network switches required by the Mainland no-proxy MVP smoke.
