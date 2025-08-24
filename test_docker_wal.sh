#!/bin/bash
# Test script to verify WAL and DELETE modes work correctly in Docker

set -e

echo "=== Docker Database Mode Testing ==="
echo "This tests both DELETE (default) and WAL modes in Docker containers"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Clean up function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker stop test-sensor-delete test-sensor-wal test-reader 2>/dev/null || true
    docker rm test-sensor-delete test-sensor-wal test-reader 2>/dev/null || true
    rm -rf test_data_delete test_data_wal
}

# Set up clean environment
cleanup
mkdir -p test_data_delete test_data_wal

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t sensor-simulator .

echo -e "\n${GREEN}=== TEST 1: DELETE Mode (Default) ===${NC}"
echo "Testing cross-boundary access (container writes, host reads)"

# Start container in DELETE mode
docker run -d \
    --name test-sensor-delete \
    -v $(pwd)/test_data_delete:/app/data \
    -e LOG_LEVEL=INFO \
    sensor-simulator

echo "Waiting for data generation..."
sleep 10

# Test reading from host
echo -e "\n${YELLOW}Reading from HOST while container writes (DELETE mode):${NC}"
for i in {1..5}; do
    COUNT=$(sqlite3 test_data_delete/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "ERROR")
    echo "  Attempt $i: Records = $COUNT"
    sleep 1
done

# Check for journal files
echo -e "\n${YELLOW}Checking journal files (DELETE mode):${NC}"
ls -la test_data_delete/*.db* 2>/dev/null || echo "Only main .db file found"

# Stop container
docker stop test-sensor-delete

# Final count
FINAL_DELETE=$(sqlite3 test_data_delete/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;")
echo -e "${GREEN}✓ DELETE mode final count: $FINAL_DELETE records${NC}"

echo -e "\n${GREEN}=== TEST 2: WAL Mode ===${NC}"
echo "Testing WAL mode in container with concurrent access"

# Start container in WAL mode
docker run -d \
    --name test-sensor-wal \
    -v $(pwd)/test_data_wal:/app/data \
    -e SENSOR_WAL=true \
    -e LOG_LEVEL=INFO \
    sensor-simulator

echo "Waiting for data generation..."
sleep 10

# Test reading from host
echo -e "\n${YELLOW}Reading from HOST while container writes (WAL mode):${NC}"
for i in {1..5}; do
    COUNT=$(sqlite3 test_data_wal/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "ERROR")
    echo "  Attempt $i: Records = $COUNT"
    sleep 1
done

# Check for WAL files
echo -e "\n${YELLOW}Checking WAL files:${NC}"
ls -la test_data_wal/*.db* 2>/dev/null || echo "No WAL files found"

# Test concurrent reader container
echo -e "\n${YELLOW}Starting reader container to test concurrent access:${NC}"
docker run -d \
    --name test-reader \
    -v $(pwd)/test_data_wal:/app/data \
    sensor-simulator \
    bash -c 'while true; do sqlite3 /app/data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" && sleep 2; done'

# Check reader logs
sleep 5
echo "Reader container output:"
docker logs --tail 5 test-reader

# Stop containers
docker stop test-sensor-wal test-reader

# Final count
FINAL_WAL=$(sqlite3 test_data_wal/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;" 2>/dev/null || echo "ERROR")
echo -e "${GREEN}✓ WAL mode final count: $FINAL_WAL records${NC}"

echo -e "\n${GREEN}=== TEST 3: Container-to-Container Access ===${NC}"

# Test both modes with multiple containers
echo -e "\n${YELLOW}Testing container-to-container communication:${NC}"

# DELETE mode container-to-container
docker run -d \
    --name test-sensor-delete \
    -v test-volume-delete:/app/data \
    sensor-simulator

sleep 5

docker run --rm \
    -v test-volume-delete:/app/data \
    sensor-simulator \
    sqlite3 /app/data/sensor_data.db "SELECT COUNT(*) as delete_mode_count FROM sensor_readings;"

docker stop test-sensor-delete
docker rm test-sensor-delete

# WAL mode container-to-container
docker run -d \
    --name test-sensor-wal \
    -v test-volume-wal:/app/data \
    -e SENSOR_WAL=true \
    sensor-simulator

sleep 5

docker run --rm \
    -v test-volume-wal:/app/data \
    sensor-simulator \
    sqlite3 /app/data/sensor_data.db "SELECT COUNT(*) as wal_mode_count FROM sensor_readings;"

docker stop test-sensor-wal
docker rm test-sensor-wal

# Clean up volumes
docker volume rm test-volume-delete test-volume-wal 2>/dev/null || true

echo -e "\n${GREEN}=== TEST 4: Mode Detection Test ===${NC}"

# Create a test script that checks which mode is active
cat > test_mode_check.sh << 'EOF'
#!/bin/bash
DB_PATH="/app/data/sensor_data.db"

echo "Checking database mode..."
MODE=$(sqlite3 $DB_PATH "PRAGMA journal_mode;" 2>/dev/null || echo "ERROR")
echo "Current mode: $MODE"

if [ "$MODE" = "wal" ]; then
    echo "✓ WAL mode confirmed"
    ls -la /app/data/*.db* | grep -E "(wal|shm)" || echo "Warning: No WAL files found"
elif [ "$MODE" = "delete" ]; then
    echo "✓ DELETE mode confirmed"
else
    echo "✗ Unexpected mode or error: $MODE"
fi
EOF

chmod +x test_mode_check.sh

echo -e "${YELLOW}Checking DELETE mode:${NC}"
docker run --rm \
    -v $(pwd)/test_data_delete:/app/data \
    -v $(pwd)/test_mode_check.sh:/test_mode_check.sh \
    sensor-simulator \
    /test_mode_check.sh

echo -e "\n${YELLOW}Checking WAL mode:${NC}"
docker run --rm \
    -v $(pwd)/test_data_wal:/app/data \
    -v $(pwd)/test_mode_check.sh:/test_mode_check.sh \
    sensor-simulator \
    /test_mode_check.sh

echo -e "\n${GREEN}=== SUMMARY ===${NC}"
echo "DELETE mode records created: $FINAL_DELETE"
echo "WAL mode records created: $FINAL_WAL"

if [ "$FINAL_DELETE" = "ERROR" ] || [ "$FINAL_WAL" = "ERROR" ]; then
    echo -e "${RED}✗ One or more tests failed!${NC}"
    echo "This might indicate issues with volume mounts or file permissions."
    exit 1
else
    echo -e "${GREEN}✓ All tests passed!${NC}"
fi

# Cleanup
rm test_mode_check.sh
cleanup

echo -e "\n${YELLOW}Recommendations:${NC}"
echo "1. Use DELETE mode (default) for better Docker compatibility"
echo "2. WAL mode works but may have issues with some storage drivers"
echo "3. For production, test with your specific Docker setup"