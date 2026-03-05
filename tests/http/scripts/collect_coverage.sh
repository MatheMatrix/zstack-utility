#!/bin/bash
# collect_coverage.sh - Stop coverage-instrumented kvmagent and collect data
#
# Usage:
#   ssh root@compute_node bash collect_coverage.sh
#   scp root@compute_node:/tmp/.coverage.kvmagent .
#   coverage report --data-file=.coverage.kvmagent
#
# This script:
#   1. Sends SIGTERM to the coverage-instrumented kvmagent
#   2. Waits for graceful shutdown (coverage data flush)
#   3. Generates coverage report
#   4. Restarts normal kvmagent daemon

set -e

COVERAGE_DATA="/tmp/.coverage.kvmagent"
PID_FILE="/tmp/kvmagent_coverage.pid"
REPORT_FILE="/tmp/kvmagent_coverage_report.txt"

echo "=== Collecting kvmagent coverage ==="

# 1. Find and stop coverage-instrumented kvmagent
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "[1/4] Sending SIGTERM to kvmagent (PID: $PID)..."
    kill -TERM "$PID" 2>/dev/null || true
else
    echo "[1/4] No PID file found, trying pkill..."
    pkill -TERM -f "kvmagent_foreground" 2>/dev/null || true
fi

# 2. Wait for shutdown (coverage needs time to flush)
echo "[2/4] Waiting for coverage data flush..."
for i in $(seq 1 15); do
    if [ -f "$COVERAGE_DATA" ]; then
        # Check if process is still running
        if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
            sleep 1
            continue
        fi
        break
    fi
    sleep 1
done

# 3. Generate report
if [ -f "$COVERAGE_DATA" ]; then
    echo "[3/4] Generating coverage report..."
    cd /usr/local/zstack/kvmagent
    coverage report \
        --data-file="$COVERAGE_DATA" \
        --include="kvmagent/kvmagent/*" \
        --omit="*/test/*" \
        | tee "$REPORT_FILE"

    echo ""
    echo "Coverage data: $COVERAGE_DATA"
    echo "Report: $REPORT_FILE"
    echo ""
    echo "To get detailed HTML report:"
    echo "  scp root@\$(hostname):$COVERAGE_DATA ."
    echo "  coverage html --data-file=.coverage.kvmagent"
else
    echo "[3/4] WARNING: No coverage data found at $COVERAGE_DATA"
    echo "  The kvmagent process may not have shut down cleanly."
fi

# 4. Restart normal kvmagent
echo "[4/4] Restarting normal kvmagent daemon..."
rm -f "$PID_FILE"
systemctl start zstack-kvmagent 2>/dev/null || true

echo "=== Done ==="
