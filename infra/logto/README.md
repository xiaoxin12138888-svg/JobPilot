# Logto isolated verification deployment

This directory is only for the ADR-007 `Logto Verification Slice — Protocol & Mainland MVP Gate`. It is not a production deployment and does not authorize adapter migration, Task 8 or Phase 3.

## Fixed artifacts

- Logto OSS: `v1.42.0`, peeled commit `3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d`
- License: Mozilla Public License 2.0
- Logto image: `ghcr.io/logto-io/logto:1.42.0@sha256:aac94e24ab7bef59be5d1809b1481b179495aaa75bb9dc2895ceae46e4117854`
- PostgreSQL reference: official `postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`

[`v1.43.0`](https://github.com/logto-io/logto/releases/tag/v1.43.0) appeared on the official release feed on 2026-08-31. This verification intentionally uses the one-month-old `v1.42.0` baseline rather than a same-day release. The selected artifact is immutable; do not replace it with `latest`, `edge`, `1`, `1.42` or a moving Compose file from repository `HEAD`.

Official sources:

- [Logto v1.42.0 release](https://github.com/logto-io/logto/releases/tag/v1.42.0)
- [Logto v1.42.0 license](https://github.com/logto-io/logto/blob/v1.42.0/LICENSE)
- [Logto v1.42.0 Dockerfile](https://github.com/logto-io/logto/blob/v1.42.0/Dockerfile)
- [Logto v1.42.0 reference Compose](https://github.com/logto-io/logto/blob/v1.42.0/docker-compose.yml)
- [Logto OSS getting started](https://docs.logto.io/logto-oss/get-started-with-oss)

The official reference Compose uses PostgreSQL 17 and starts Logto with `npm run cli db seed -- --swe && npm start`. It defaults to a moving Logto tag and has no database volume, so this verification file pins both image references by digest and adds a dedicated persistence volume. PostgreSQL is not published to the host and is a separate ownership boundary from the JobPilot business database.

Official documentation lists 2 vCPU, 8 GiB RAM and 256 GiB disk as minimum recommended OSS hardware. The fixed source requires Node `^22.14.0`, while the official container supplies its own Node runtime. The fixed `v1.42.0` reference Compose uses `postgres:17-alpine`; this verification does not infer support or non-support for other PostgreSQL majors.

The exact tag, source and registry checks are retained in [Official artifact evidence](OFFICIAL_ARTIFACT_EVIDENCE.md).

## Local-only commands

Prerequisite: a modern Docker Engine and `docker compose` CLI capable of Linux containers. The current validation host did not have Docker, Podman, a usable WSL distribution or PostgreSQL when this baseline was written; file creation alone is not runtime evidence.

1. Copy `verification.env.example` to ignored `infra/logto/.env.logto-verification`.
2. Replace `LOGTO_DB_PASSWORD` with a generated URL-safe local-only value. Do not put it in evidence or Git.
3. Validate interpolation before starting:

   ```powershell
   docker compose --env-file infra/logto/.env.logto-verification -f infra/logto/compose.verification.yml config --quiet
   ```

4. Start the isolated services:

   ```powershell
   docker compose --env-file infra/logto/.env.logto-verification -f infra/logto/compose.verification.yml up -d
   ```

5. Inspect status without copying credentials or raw provider payloads into evidence:

   ```powershell
   docker compose --env-file infra/logto/.env.logto-verification -f infra/logto/compose.verification.yml ps
   ```

Core and Admin Console bind only to `127.0.0.1:3001` and `127.0.0.1:3002`. PostgreSQL has no published host port; the internal Docker network also blocks runtime container egress during this connector-free baseline. `docker compose down` preserves the dedicated identity volume; volume deletion is a separate destructive cleanup and is not part of normal verification.

The fixed official reference Compose also sets `user: postgres`. Empty-volume initialization and restart persistence still require live verification; if the pinned image reports a volume ownership failure, record it rather than silently changing the image or running the service as root.

## Verification boundary

The initial loopback HTTP endpoint is sufficient only to prove fixed-version startup and PostgreSQL connectivity. Persistence requires a write, container restart and read-back check against the dedicated volume. Current JobPilot provider configuration requires a trusted HTTPS issuer, so Web/Extension integration remains `BLOCKED` until an exact local HTTPS boundary is configured and its discovery metadata is verified. Do not weaken the existing HTTPS validator to make this Compose file pass.

Configure only one Web confidential application, one Extension public application with no secret, and one JobPilot API resource. Do not enable social login, Google, GitHub, WeChat, enterprise SSO, organizations, RBAC, MFA or SMS. Use only an isolated local email/password test account and never record its raw identifiers or credentials.
