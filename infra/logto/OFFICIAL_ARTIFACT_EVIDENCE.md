# Official artifact evidence — Logto verification baseline

- Checked at: `2026-08-31T20:08:46.1173300+08:00`
- Network operation: read-only official GitHub raw/tag sources and container registries
- Credentials retained: `NO` — registry bearer tokens and response bodies containing them were never printed or stored

## Git tag evidence

Command:

```powershell
git ls-remote --tags https://github.com/logto-io/logto.git refs/tags/v1.42.0 'refs/tags/v1.42.0^{}' refs/tags/v1.43.0 'refs/tags/v1.43.0^{}'
```

Redacted-safe output (Git object IDs and public refs only):

```text
90a2a98bad2b23d3c3d55a48d9bc293f0f2bb05f  refs/tags/v1.42.0
3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d  refs/tags/v1.42.0^{}
b18b66361f8eca8e57b6504b493fb70963cf98ba  refs/tags/v1.43.0
d066df7d26d596b6ba7ad0bdfaaecfda9c612226  refs/tags/v1.43.0^{}
```

The verification baseline selects the peeled `v1.42.0` commit `3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d`. `v1.43.0` appeared on the [official release feed](https://github.com/logto-io/logto/releases.atom) at `2026-08-31T10:39:03Z`; it was not selected because the fixed baseline intentionally avoids same-day release churn.

## Commit-pinned source evidence

The following public files were read from the selected tag/commit:

- [LICENSE](https://github.com/logto-io/logto/blob/3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d/LICENSE): first line `Mozilla Public License Version 2.0`
- [package.json](https://github.com/logto-io/logto/blob/3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d/package.json): Node engine `^22.14.0`
- [Dockerfile](https://github.com/logto-io/logto/blob/3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d/Dockerfile): official Logto container source
- [docker-compose.yml](https://github.com/logto-io/logto/blob/3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d/docker-compose.yml):
  - Logto image expression: `svhd/logto:${TAG-latest}`
  - PostgreSQL image: `postgres:17-alpine`
  - startup command: `npm run cli db seed -- --swe && npm start`

The official Compose moving-tag expression is recorded as evidence only and is not used by JobPilot.

## Registry manifest evidence

The OCI/Docker registry `Docker-Content-Digest` response headers returned:

```text
ghcr.io/logto-io/logto:1.42.0
sha256:aac94e24ab7bef59be5d1809b1481b179495aaa75bb9dc2895ceae46e4117854

docker.io/library/postgres:17-alpine
sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73
```

The verification Compose uses `tag@sha256` for both images. No moving tag is accepted as the immutable baseline.

## Runtime recommendation source

[Logto OSS getting started](https://docs.logto.io/logto-oss/get-started-with-oss) listed `2 vCPU`, `8 GiB RAM` and `256 GiB disk` as minimum recommended hardware when checked. This is recorded as an upstream recommendation, not evidence that the current host meets it or that a smaller isolated development run cannot start.
