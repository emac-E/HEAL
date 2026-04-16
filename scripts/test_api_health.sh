#!/bin/bash
#
# Simple test to verify lightspeed API is responding
# Creates a minimal test config and runs a single evaluation
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVAL_ROOT="/home/emackey/Work/lightspeed-core/lightspeed-evaluation"
TEST_OUTPUT="/tmp/heal_api_test_$(date +%s)"

echo "=========================================="
echo "Lightspeed API Health Check"
echo "=========================================="
echo ""

# Check if okp-mcp container is running
echo "1. Checking okp-mcp container status..."
if ! curl -s http://localhost:8001/mcp > /dev/null 2>&1; then
    echo "❌ okp-mcp not responding on http://localhost:8001"
    echo "   Start with: cd ~/Work/lscore-deploy/local && podman-compose up -d okp-mcp"
    exit 1
fi
echo "✅ okp-mcp container is running"
echo ""

# Create minimal test config
echo "2. Creating minimal test config..."
TEST_CONFIG="${TEST_OUTPUT}/test_config.yaml"
mkdir -p "${TEST_OUTPUT}"

cat > "${TEST_CONFIG}" << 'EOF'
- conversation_group_id: API_HEALTH_TEST
  turns:
  - turn_id: "1"
    query: "What is RHEL?"
    expected_response: "Red Hat Enterprise Linux (RHEL) is a Linux distribution."
    turn_metrics:
    - custom:answer_correctness
EOF

echo "✅ Test config created at ${TEST_CONFIG}"
echo ""

# Clear caches
echo "3. Clearing API cache..."
rm -rf "${EVAL_ROOT}/.caches/api_cache/"*
mkdir -p "${EVAL_ROOT}/.caches/api_cache"
echo "✅ Cache cleared"
echo ""

# Run single evaluation
echo "4. Running test evaluation..."
echo "   (This will call the lightspeed API with a simple question)"
echo ""

cd "${EVAL_ROOT}"

if uv run lightspeed-eval \
    --system-config "config/system_okp_mcp_agent.yaml" \
    --eval-data "${TEST_CONFIG}" \
    --output-dir "${TEST_OUTPUT}" \
    --metrics "custom:answer_correctness" 2>&1 | tee "${TEST_OUTPUT}/test.log"; then

    # Check if evaluation actually succeeded (not just exit code 0)
    if grep -q "Evaluation failed\|Error:" "${TEST_OUTPUT}/test.log" 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "❌ API Health Check: FAILED"
        echo "=========================================="
        echo ""
        echo "Evaluation reported errors. Check logs at: ${TEST_OUTPUT}/test.log"
        echo ""
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "✅ API Health Check: PASSED"
    echo "=========================================="
    echo ""
    echo "The lightspeed API is responding correctly!"
    echo ""
    echo "Output saved to: ${TEST_OUTPUT}"
    echo "View results: cat ${TEST_OUTPUT}/test.log"
    echo ""
    exit 0
else
    echo ""
    echo "=========================================="
    echo "❌ API Health Check: FAILED"
    echo "=========================================="
    echo ""
    echo "The evaluation failed. Check logs at: ${TEST_OUTPUT}/test.log"
    echo ""

    # Check for 500 errors
    if grep -q "500\|Internal Server Error" "${TEST_OUTPUT}/test.log" 2>/dev/null; then
        echo "⚠️  Detected HTTP 500 errors - API is experiencing issues"
        echo "   This is an infrastructure problem, not a code issue"
    fi

    echo ""
    exit 1
fi
