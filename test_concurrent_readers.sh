#!/bin/bash
# Test concurrent readers while the main app writes

echo "Starting sensor simulator in background..."
uv run main.py --config config/config.yaml --identity config/node-identity.json &
MAIN_PID=$!

sleep 2

echo "Starting 10 concurrent readers..."
for i in {1..10}; do
    (
        while kill -0 $MAIN_PID 2>/dev/null; do
            COUNT=$(echo "SELECT COUNT(*) FROM sensor_readings;" | sqlite3 "file:data/sensor_data.db?mode=ro" 2>/dev/null)
            echo "Reader $i: $COUNT readings"
            sleep 0.5
        done
    ) &
done

echo "Running for 10 seconds..."
sleep 10

echo "Stopping simulator..."
kill $MAIN_PID 2>/dev/null

wait

echo "Final count:"
echo "SELECT COUNT(*) FROM sensor_readings;" | sqlite3 data/sensor_data.db
