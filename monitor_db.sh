#!/bin/bash
# Real-time database monitoring script

DB_PATH="data/sensor_data.db"

echo "=== Real-time Database Monitor ==="
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "=== Database Status at $(date '+%Y-%m-%d %H:%M:%S') ==="
    echo ""
    
    # File info
    if [ -f "$DB_PATH" ]; then
        echo "📁 File Info:"
        ls -lh "$DB_PATH" | awk '{print "  Size: " $5 "\n  Modified: " $6 " " $7 " " $8}'
        echo ""
        
        # Record counts (using read-only mode)
        echo "📊 Record Statistics:"
        sqlite3 "file:$DB_PATH?mode=ro" 2>/dev/null <<EOF
.mode column
.headers on
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT sensor_id) as sensors,
    SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) as anomalies
FROM sensor_readings;
EOF
        echo ""
        
        # Recent readings (using read-only mode)
        echo "📈 Last 5 Readings:"
        sqlite3 "file:$DB_PATH?mode=ro" 2>/dev/null <<EOF
.mode column
.headers on
SELECT 
    datetime(timestamp, 'localtime') as time,
    sensor_id,
    printf('%.1f', temperature) as temp,
    printf('%.1f', humidity) as humid,
    CASE WHEN anomaly_flag = 1 THEN '⚠️ ' || anomaly_type ELSE '✓' END as status
FROM sensor_readings 
ORDER BY timestamp DESC 
LIMIT 5;
EOF
        
        # Anomaly rate (using read-only mode)
        echo ""
        echo "🎯 Anomaly Rate:"
        sqlite3 "file:$DB_PATH?mode=ro" 2>/dev/null <<EOF
.mode column
SELECT 
    printf('%.2f%%', 100.0 * SUM(anomaly_flag) / COUNT(*)) as rate
FROM sensor_readings;
EOF
    else
        echo "❌ Database file not found at $DB_PATH"
    fi
    
    sleep 2
done