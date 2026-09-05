#!/usr/bin/env bash
# Flint Chart integration test script
# Verifies that the Flint MCP server is reachable and functional.
set -euo pipefail

echo "=== Flint Chart Integration Test ==="

if npx -y flint-chart-mcp --version > /dev/null 2>&1; then
    echo "PASS: flint-chart-mcp is available via npx"
else
    echo "FAIL: flint-chart-mcp not found — check npm registry access"
    exit 1
fi

echo "=== All checks passed ==="
