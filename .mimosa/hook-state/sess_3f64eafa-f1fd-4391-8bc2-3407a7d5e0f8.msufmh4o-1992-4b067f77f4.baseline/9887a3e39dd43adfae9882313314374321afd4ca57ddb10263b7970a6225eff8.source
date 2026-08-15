// GenBI Cube project — data models live in ./schema/*.yml (10 cubes over the
// seeded analytics tables). ADR 007 documents the pivot to Cube-native
// models; ADR 008 documents the per-tenant data path below.
//
// Tenant isolation on data queries (/load):
//   1. The backend mints JWTs carrying a `tenantId` claim (Cube surfaces
//      custom claims as securityContext).
//   2. contextToOrchestratorId keys the orchestrator — and therefore the
//      driver pool — by tenant, so tenants never share connections.
//   3. driverFactory passes the pg `options` connection parameter setting
//      app.current_tenant_id — the exact GUC the Postgres RLS policies
//      consume (Phase 8b).
//
// Failure mode is CLOSED: if the GUC is ever missing, RLS returns zero rows
// for that query — it can never return another tenant's data. Metadata
// requests (/meta, no tenant claim) use the plain driver.

const PostgresDriver = require("@cubejs-backend/postgres-driver");

function baseDbConfig() {
  return {
    host: process.env.CUBEJS_DB_HOST,
    port: process.env.CUBEJS_DB_PORT ? parseInt(process.env.CUBEJS_DB_PORT, 10) : 5432,
    user: process.env.CUBEJS_DB_USER,
    password: process.env.CUBEJS_DB_PASS,
    database: process.env.CUBEJS_DB_NAME,
  };
}

module.exports = {
  apiSecret: process.env.CUBEJS_API_SECRET,
  devMode: process.env.CUBEJS_DEV_MODE === "true",

  contextToOrchestratorId: ({ securityContext }) =>
    (securityContext && securityContext.tenantId) || "anonymous",

  driverFactory: ({ securityContext }) => {
    const tenantId = securityContext && securityContext.tenantId;
    const config = baseDbConfig();
    if (tenantId) {
      // Session GUC on every pooled connection — consumed by the
      // tenant_isolation RLS policies.
      config.options = `-c app.current_tenant_id=${tenantId}`;
    }
    return new PostgresDriver(config);
  },
};
