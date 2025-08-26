#!/bin/bash
# Test concurrent readers against an EXISTING database
# This script only reads - it does NOT start the sensor simulator

set -e

# Configuration
DB_PATH="${DB_PATH:-data/sensor_data.db}"
NUM_READERS="${NUM_READERS:-10}"
DURATION="${DURATION:-30}"
INTERVAL="${INTERVAL:-0.5}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Concurrent Database Reader Test${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}✗ Database not found: $DB_PATH${NC}"
    echo -e "${YELLOW}Please run the sensor simulator first to create the database${NC}"
    echo ""
    echo "To start the sensor simulator:"
    echo "  uv run main.py --config config/config.yaml --identity config/node-identity.json"
    echo ""
    echo "Or with Docker:"
    echo "  docker compose up -d"
    exit 1
fi

# Check if database is accessible
INITIAL_COUNT=$(sqlite3 "file:${DB_PATH}?mode=ro" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
if [ "$INITIAL_COUNT" = "0" ]; then
    echo -e "${YELLOW}⚠ Database is empty or not accessible${NC}"
    echo "Make sure the database has been initialized with at least one reading"
    exit 1
fi

echo -e "${GREEN}✓${NC} Database found: $DB_PATH"
echo -e "${GREEN}✓${NC} Initial record count: $INITIAL_COUNT"
echo ""

# Check if database is being actively written to
echo -e "${BLUE}Checking for active writes...${NC}"
sleep 2
NEW_COUNT=$(sqlite3 "file:${DB_PATH}?mode=ro" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
if [ "$NEW_COUNT" -gt "$INITIAL_COUNT" ]; then
    RATE=$(( (NEW_COUNT - INITIAL_COUNT) / 2 ))
    echo -e "${GREEN}✓${NC} Database is being written to (~$RATE records/sec)"
else
    echo -e "${YELLOW}!${NC} No new writes detected - database appears idle"
fi
echo ""

# Start test
echo -e "${BLUE}Starting concurrent reader test:${NC}"
echo "  • Readers: $NUM_READERS"
echo "  • Duration: $DURATION seconds"
echo "  • Interval: $INTERVAL seconds"
echo ""

# Function for reader process
reader_process() {
    local READER_ID=$1
    local END_TIME=$(($(date +%s) + DURATION))
    local READ_COUNT=0
    local ERROR_COUNT=0

    while [ $(date +%s) -lt $END_TIME ]; do
        # Try to read from database
        if RESULT=$(sqlite3 "file:${DB_PATH}?mode=ro" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null); then
            READ_COUNT=$((READ_COUNT + 1))
            echo -e "${GREEN}Reader $READER_ID:${NC} $RESULT records (read #$READ_COUNT)"
        else
            ERROR_COUNT=$((ERROR_COUNT + 1))
            echo -e "${RED}Reader $READER_ID:${NC} Read failed (error #$ERROR_COUNT)"
        fi

        sleep $INTERVAL
    done

    echo -e "${BLUE}Reader $READER_ID complete:${NC} $READ_COUNT reads, $ERROR_COUNT errors"
}

# Start readers in background
echo -e "${YELLOW}Starting $NUM_READERS concurrent readers...${NC}"
for i in $(seq 1 $NUM_READERS); do
    reader_process $i &
done

# Show progress
echo ""
echo -e "${YELLOW}Test running for $DURATION seconds...${NC}"
echo "(Press Ctrl+C to stop early)"
echo ""

# Wait for all readers to complete
wait

# Final statistics
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
FINAL_COUNT=$(sqlite3 "file:${DB_PATH}?mode=ro" "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "0")
RECORDS_ADDED=$((FINAL_COUNT - INITIAL_COUNT))

echo -e "${GREEN}Test Complete!${NC}"
echo ""
echo "Summary:"
echo "  • Initial records: $INITIAL_COUNT"
echo "  • Final records: $FINAL_COUNT"
echo "  • Records added during test: $RECORDS_ADDED"
echo "  • Readers: $NUM_READERS"
echo "  • Test duration: $DURATION seconds"

if [ $RECORDS_ADDED -gt 0 ]; then
    WRITE_RATE=$((RECORDS_ADDED / DURATION))
    echo "  • Average write rate: ~$WRITE_RATE records/sec"
fi
