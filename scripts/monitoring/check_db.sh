#!/bin/bash
# Quick database check script

DB_PATH="data/sensor_data.db"

echo "=== Database Quick Check ==="
echo ""

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found at $DB_PATH"
    echo "   Run the simulator first: uv run main.py"
    exit 1
fi

echo "📊 Database Summary:"
sqlite3 "file:$DB_PATH?mode=ro" <<EOF
.headers on
.mode column
SELECT
    COUNT(*) as total_readings,
    MIN(timestamp) as first_reading,
    MAX(timestamp) as last_reading,
    printf('%.2f', AVG(temperature)) as avg_temp,
    printf('%.2f%%', 100.0 * SUM(anomaly_flag) / COUNT(*)) as anomaly_rate
FROM sensor_readings;
EOF

echo ""
echo "🏭 Readings by Manufacturer:"
sqlite3 "file:$DB_PATH?mode=ro" <<EOF
.headers on
.mode column
SELECT
    manufacturer,
    COUNT(*) as count,
    printf('%.2f%%', 100.0 * SUM(anomaly_flag) / COUNT(*)) as anomaly_rate
FROM sensor_readings
GROUP BY manufacturer;
EOF

echo ""
echo "⚠️  Anomaly Types:"
sqlite3 "file:$DB_PATH?mode=ro" <<EOF
.headers on
.mode column
SELECT
    COALESCE(anomaly_type, 'Normal') as type,
    COUNT(*) as count
FROM sensor_readings
GROUP BY anomaly_type
ORDER BY count DESC;
EOF

echo ""
echo "📈 Hourly Statistics:"
sqlite3 "file:$DB_PATH?mode=ro" <<EOF
.headers on
.mode column
SELECT
    strftime('%H', timestamp) as hour,
    COUNT(*) as readings,
    printf('%.1f', AVG(temperature)) as avg_temp,
    printf('%.1f', AVG(humidity)) as avg_humidity
FROM sensor_readings
GROUP BY hour
ORDER BY hour;
EOF
