#!/bin/bash
# Test script specifically for Linux to verify WAL mode works correctly

set -e

echo "=== Linux WAL Mode Testing ==="
echo "This test verifies that WAL mode works correctly on Linux"
echo ""

# Detect platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "✅ Running on Linux - WAL mode should work well"
    PLATFORM="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "⚠️  Running on macOS - WAL may have issues with Docker Desktop"
    PLATFORM="mac"
else
    echo "⚠️  Running on Windows - WAL may have issues with Docker Desktop"
    PLATFORM="windows"
fi

echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Clean up function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker stop wal-test-linux 2>/dev/null || true
    docker rm wal-test-linux 2>/dev/null || true
    rm -rf test_wal_linux
}

# Set up clean environment
cleanup
mkdir -p test_wal_linux

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t sensor-simulator . >/dev/null 2>&1

echo -e "\n${GREEN}=== TEST: WAL Mode with Concurrent Access ===${NC}"

# Start container in WAL mode
echo "Starting container with WAL mode enabled..."
docker run -d \
    --name wal-test-linux \
    -v $(pwd)/test_wal_linux:/app/data \
    -e SENSOR_WAL=true \
    -e LOG_LEVEL=INFO \
    sensor-simulator

echo "Waiting for database initialization..."
sleep 5

# Check journal mode
echo -e "\n${YELLOW}Checking journal mode:${NC}"
MODE=$(sqlite3 test_wal_linux/sensor_data.db "PRAGMA journal_mode;" 2>/dev/null || echo "ERROR")
echo "Journal mode: $MODE"

if [ "$MODE" = "wal" ]; then
    echo -e "${GREEN}✅ WAL mode confirmed${NC}"
else
    echo -e "${RED}❌ WAL mode not active or error${NC}"
fi

# Check for WAL files
echo -e "\n${YELLOW}Checking for WAL files:${NC}"
if [ -f test_wal_linux/sensor_data.db-wal ]; then
    echo -e "${GREEN}✅ WAL file exists${NC}"
    ls -lh test_wal_linux/*.db* | grep -E "(wal|shm)"
else
    echo -e "${YELLOW}⚠️  No WAL file found (may be checkpointed)${NC}"
fi

# Test concurrent reads while container writes
echo -e "\n${YELLOW}Testing concurrent reads from host:${NC}"
SUCCESS_COUNT=0
LOCK_COUNT=0

for i in {1..10}; do
    # Try to read with short timeout
    if OUTPUT=$(timeout 1 sqlite3 test_wal_linux/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" 2>&1); then
        echo "  Read $i: $OUTPUT records"
        ((SUCCESS_COUNT++))
    else
        if [[ "$OUTPUT" == *"locked"* ]]; then
            echo "  Read $i: Database locked"
            ((LOCK_COUNT++))
        else
            echo "  Read $i: Error - $OUTPUT"
        fi
    fi
    sleep 0.5
done

echo -e "\n${YELLOW}Results:${NC}"
echo "  Successful reads: $SUCCESS_COUNT/10"
echo "  Lock errors: $LOCK_COUNT/10"

# Platform-specific expectations
if [ "$PLATFORM" = "linux" ]; then
    if [ $SUCCESS_COUNT -ge 8 ]; then
        echo -e "${GREEN}✅ PASS: WAL mode works well on Linux${NC}"
        echo "  Concurrent reads succeeded with minimal locks"
    else
        echo -e "${YELLOW}⚠️  WARNING: More locks than expected on Linux${NC}"
        echo "  This might indicate filesystem or Docker configuration issues"
    fi
else
    if [ $SUCCESS_COUNT -lt 5 ]; then
        echo -e "${YELLOW}⚠️  Expected: WAL mode has issues on $PLATFORM with Docker Desktop${NC}"
        echo "  Use DELETE mode (default) for better compatibility"
    else
        echo -e "${GREEN}✅ Surprisingly good results on $PLATFORM${NC}"
    fi
fi

# Test write performance
echo -e "\n${YELLOW}Checking write performance:${NC}"
docker logs --tail 20 wal-test-linux 2>&1 | grep -E "(readings|batch|commit)" || true

# Stop container
docker stop wal-test-linux >/dev/null 2>&1

# Final check
FINAL_COUNT=$(sqlite3 test_wal_linux/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
echo -e "\n${YELLOW}Final database state:${NC}"
echo "  Total records: $FINAL_COUNT"

# Recommendations
echo -e "\n${GREEN}=== RECOMMENDATIONS ===${NC}"
if [ "$PLATFORM" = "linux" ]; then
    echo "✅ On Linux: WAL mode is recommended for better concurrent access"
    echo "   Use: docker run -e SENSOR_WAL=true ..."
else
    echo "⚠️  On $PLATFORM: Use DELETE mode (default) for Docker Desktop"
    echo "   Use: docker run ... (don't set SENSOR_WAL)"
fi

# Cleanup
cleanup

echo -e "\n${GREEN}Test complete!${NC}"