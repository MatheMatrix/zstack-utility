#!/bin/bash
# run_kvmagent_with_coverage.sh - Start kvmagent under coverage instrumentation
#
# Usage:
#   scp this script + kvmagent_foreground.py to compute node
#   ssh root@compute_node bash run_kvmagent_with_coverage.sh
#
# Prerequisites:
#   pip install coverage (on the compute node)
#   systemctl stop zstack-kvmagent (stop the normal daemon)
#
# The script:
#   1. Stops existing kvmagent
#   2. Starts kvmagent under coverage run in foreground
#   3. Writes PID to /tmp/kvmagent_coverage.pid for later SIGTERM
#
# After tests, run collect_coverage.sh to SIGTERM and collect .coverage

set -e

KVMAGENT_DIR="/usr/local/zstack/kvmagent"
COVERAGE_DATA="/tmp/.coverage.kvmagent"
PID_FILE="/tmp/kvmagent_coverage.pid"
LOG_FILE="/tmp/kvmagent_coverage.log"

echo "=== kvmagent coverage runner ==="

# 1. Stop existing kvmagent
echo "[1/3] Stopping existing kvmagent..."
systemctl stop zstack-kvmagent 2>/dev/null || true
sleep 1

# Kill any lingering kvmagent processes
pkill -f "kvmagent_foreground" 2>/dev/null || true
pkill -f "kvmagentdaemon" 2>/dev/null || true
sleep 1

# 2. Check coverage is installed
if ! command -v coverage &>/dev/null; then
    echo "ERROR: coverage not installed. Run: pip install coverage"
    exit 1
fi

# 3. Copy foreground launcher if not present
FOREGROUND_PY="$KVMAGENT_DIR/kvmagent/kvmagent_foreground.py"
if [ ! -f "$FOREGROUND_PY" ]; then
    echo "ERROR: $FOREGROUND_PY not found. SCP it first."
    exit 1
fi

# 4. Start kvmagent under coverage
echo "[2/3] Starting kvmagent under coverage instrumentation..."
cd "$KVMAGENT_DIR"

# Remove old coverage data
rm -f "$COVERAGE_DATA"

# Run in background, redirect output to log
nohup coverage run \
    --source=kvmagent/kvmagent \
    --data-file="$COVERAGE_DATA" \
    -m kvmagent.kvmagent_foreground \
    > "$LOG_FILE" 2>&1 &

KVMAGENT_PID=$!
echo "$KVMAGENT_PID" > "$PID_FILE"

echo "[3/3] kvmagent started with PID $KVMAGENT_PID"
echo "  Coverage data: $COVERAGE_DATA"
echo "  Log file: $LOG_FILE"
echo "  PID file: $PID_FILE"

# Wait for port 7070 to be ready
echo "Waiting for port 7070..."
for i in $(seq 1 30); do
    if ss -tlnp | grep -q ":7070 "; then
        echo "kvmagent is ready on port 7070 (took ${i}s)"
        exit 0
    fi
    sleep 1
done

echo "WARNING: Port 7070 not ready after 30s. Check $LOG_FILE"
exit 1
