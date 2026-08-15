# ADR 005: PostgreSQL image with both pgvector and Apache AGE

- **Status:** Accepted
- **Date:** 2026-08-05
- **Supersedes:** the implicit decision in the initial commit to use
  `pgvector/pgvector:pg16` while running `CREATE EXTENSION age` in `init.sql`.

## Context

The platform relies on two PostgreSQL extensions simultaneously:

- **pgvector** — stores schema/example embeddings for NL2SQL semantic search
  (`schema_embeddings.embedding VECTOR(1536)`, `agent_examples.embedding`).
- **Apache AGE** — property graph for data lineage and downstream-impact
  analysis (`backend/app/db/graph_schema.py`, graph `genbi_graph`).

The initial `docker-compose.*.yml` used `pgvector/pgvector:pg16`, which bundles
pgvector **only**. As a result `init.sql:11` (`CREATE EXTENSION age;`) and
`LOAD 'age';` failed on first container boot, the lineage graph could never be
created, and `init_age_graph()` crashed any code path that touched lineage.

## Decision

Build a **custom Postgres image** that layers Apache AGE onto the pgvector
image, rather than choosing one extension's stock image over the other.

`infra/postgres/Dockerfile`:

```dockerfile
FROM pgvector/pgvector:pg16
RUN apk add --no-cache --virtual .age-build build-base clang llvm-dev git coreutils \
 && git clone --depth 1 --branch PG16 https://github.com/apache/age /age-src \
 && cd /age-src && make PG_CONFIG=/usr/local/bin/pg_config install \
 && cd / && rm -rf /age-src && apk del .age-build
```

Both `infra/docker-compose.dev.yml` and `infra/docker-compose.yml` now
`build: ./postgres` with image tag `genbi/postgres-pgvector-age:pg16`.

### Defense-in-depth: AGE is optional at boot

`init.sql` guards the extension so a missing AGE degrades gracefully instead of
crashing DB init — controlled by `GENBI_ENABLE_AGE` (default `true`). This
keeps dev fast (AGE build is the slowest image layer) and lets a contributor
without AGE still bring up the rest of the stack.

## Alternatives considered

1. **`apache/age:PG16` + build pgvector into it** — symmetric to the chosen
   approach, but AGE's upstream image is less frequently maintained and the
   pgvector build path is less battle-tested. Rejected.
2. **Drop AGE, use recursive CTEs for lineage** — would lose the property-graph
   query model (multi-hop impact analysis) that the graph layer is built around.
   Rejected; lineage is a documented capability.
3. **Run AGE in a separate Postgres instance** — doubles operational surface
   (two DBs, two backup strategies, cross-DB joins impossible). Rejected.

## Consequences

- **Build time:** the first `docker compose build` compiles AGE from source
  (~2–3 min). Cached thereafter.
- **Maintenance:** the AGE git branch (`PG16`) must track AGE releases; bumping
  Postgres major versions requires rebuilding AGE against the new headers.
- **Roles:** `init.sql` grants `ag_catalog` usage to `PUBLIC` (dev convenience).
  Production should restrict this to a dedicated `age_admin` role.
- **Verification:** `infra/postgres/Dockerfile` ends with a
  `RUN test -f $(pg_config --pkglibdir)/age.so` so a broken AGE release fails
  the image build, not a runtime boot.
