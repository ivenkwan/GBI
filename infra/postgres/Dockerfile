# PostgreSQL 16 with BOTH pgvector and Apache AGE.
#
# The official pgvector image ships pgvector only; Apache AGE is absent, so
# `CREATE EXTENSION age` in init.sql fails on first boot. This image layers
# AGE on top of pgvector so both extensions coexist (required for the
# lineage graph in backend/app/db/graph_schema.py).
#
# Build pin: AGE is built from source against this image's PG headers. Tag
# advances with AGE releases — bump together with the AGE_SUPERUSER role grant
# in infra/postgres/init.sql.
FROM pgvector/pgvector:pg16

# Build deps for AGE, then compile AGE against the bundled PostgreSQL, then
# strip the build deps to keep the image small.
RUN apk add --no-cache --virtual .age-build \
        build-base \
        clang \
        llvm-dev \
        git \
        coreutils \
    && git clone --depth 1 --branch PG16 https://github.com/apache/age /age-src \
    && cd /age-src \
    && make PG_CONFIG=/usr/local/bin/pg_config install \
    && cd / \
    && rm -rf /age-src \
    && apk del .age-build

# Verify the .so is installed so the image fails fast at build time if AGE
# ever stops shipping a PG16 branch.
RUN test -f $(pg_config --pkglibdir)/age.so
