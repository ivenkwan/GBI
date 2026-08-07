# PostgreSQL 16 with BOTH pgvector and Apache AGE.
#
# The official pgvector image ships pgvector only; Apache AGE is absent, so
# `CREATE EXTENSION age` in init.sql fails on first boot. This image layers
# AGE on top of pgvector so both extensions coexist (required for the
# lineage graph in backend/app/db/graph_schema.py).
#
# Base image is Debian 12 (bookworm) — use apt-get, NOT apk (Alpine).
#
# Build pin: AGE is built from source against this image's PG headers. Tag
# advances with AGE releases — bump together with the AGE_SUPERUSER role grant
# in infra/postgres/init.sql.
FROM pgvector/pgvector:pg16

# Build deps for AGE, then compile AGE against the bundled PostgreSQL, then
# strip the build deps to keep the image small. pg_config is at /usr/bin on
# the pgvector Debian image (NOT /usr/local/bin as on Alpine variants).
#
# postgresql-server-dev-16 is required: the pgvector base image is a runtime
# image and does not ship postgres.h / the server headers AGE compiles against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        clang \
        llvm-15-dev \
        libllvm15 \
        postgresql-server-dev-16 \
        git \
        ca-certificates \
        libreadline-dev \
        zlib1g-dev \
        flex \
        bison \
    && git clone --depth 1 --branch PG16 https://github.com/apache/age /age-src \
    && cd /age-src \
    && make PG_CONFIG=$(command -v pg_config) install \
    && cd / \
    && rm -rf /age-src \
    && apt-get purge -y build-essential clang llvm-15-dev libllvm15 \
        postgresql-server-dev-16 flex bison \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Verify the .so is installed so the image fails fast at build time if AGE
# ever stops shipping a PG16 branch.
RUN test -f $(pg_config --pkglibdir)/age.so
