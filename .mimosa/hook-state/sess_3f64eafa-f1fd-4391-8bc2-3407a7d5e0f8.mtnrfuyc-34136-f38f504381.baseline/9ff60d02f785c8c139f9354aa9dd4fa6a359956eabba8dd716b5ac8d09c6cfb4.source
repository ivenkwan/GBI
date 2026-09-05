module.exports = {
  // Data source — replace with actual connection
  data_source: process.env.CUBEJS_DB_URL || "postgresql://genbi:genbi@localhost:5432/genbi",

  // Import metrics from dbt MetricFlow manifest
  semantic_layer_sync: {
    dbt: {
      manifest_path: process.env.CUBEJS_DBT_MANIFEST_PATH || "../dbt/target/manifest.json",
    },
  },
};
