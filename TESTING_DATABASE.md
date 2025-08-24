# Testing Database Writes - Local Testing Guide

This guide shows multiple ways to verify that the sensor simulator is writing to the database correctly.

## Quick Start Test

```bash
# 1. Start the simulator
uv run main.py --config config/config.yaml --identity config/identity.json

# 2. In another terminal, check the database
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

## Method 1: Watch Database Growth

```bash
# Watch file size and record count in real-time
watch -n 1 'ls -lh data/sensor_data.db && sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"'
```

## Method 2: Use Monitoring Scripts

### Real-time Monitor
```bash
# Run the included monitor script
./monitor_db.sh
```

This shows:
- File size and modification time
- Total records, sensors, and anomalies
- Last 5 readings with timestamps
- Current anomaly rate

### Quick Check
```bash
# Run quick database check
./check_db.sh
```

This provides:
- Database summary with first/last readings
- Readings by manufacturer
- Anomaly type distribution
- Hourly statistics

## Method 3: HTTP Monitoring API

```bash
# Start with monitoring enabled
MONITORING_ENABLED=true uv run main.py

# Check endpoints (in another terminal)
curl http://localhost:8080/healthz    # Health status
curl http://localhost:8080/db_stats   # Database statistics
curl http://localhost:8080/metricz    # Metrics
curl http://localhost:8080/samplez    # Recent samples
```

## Method 4: Direct SQL Queries

```bash
# Connect to database
sqlite3 data/sensor_data.db

# Run queries
.headers on
.mode column

-- Check record count
SELECT COUNT(*) FROM sensor_readings;

-- View recent readings
SELECT datetime(timestamp, 'localtime') as time, 
       sensor_id, 
       temperature, 
       humidity,
       anomaly_flag
FROM sensor_readings 
ORDER BY timestamp DESC 
LIMIT 10;

-- Check write rate (readings per minute)
SELECT 
    strftime('%Y-%m-%d %H:%M', timestamp) as minute,
    COUNT(*) as readings
FROM sensor_readings
GROUP BY minute
ORDER BY minute DESC
LIMIT 5;
```

## Method 5: Test Concurrent Access

### Test with DELETE mode (default)
```bash
# Terminal 1: Start simulator
uv run main.py

# Terminal 2: Run external reader
uv run test_external_reader.py
```

### Test with WAL mode (better concurrency)
```bash
# Terminal 1: Start simulator with WAL
SENSOR_WAL=true uv run main.py

# Terminal 2: Run external reader
uv run test_external_reader.py

# Terminal 3: Run another reader simultaneously
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
```

## Method 6: Tail the Logs

```bash
# Watch for database writes in logs
tail -f logs/sensor_simulator.log | grep -E "(stored|committed|readings)"

# Or with debug mode for detailed info
LOG_LEVEL=DEBUG uv run main.py 2>&1 | grep -E "storing|commit|batch"
```

## Method 7: Docker Testing

```bash
# Run in Docker with volume mount
docker run -v $(pwd)/data:/app/data sensor-simulator

# Check database from host
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"

# Or with WAL mode
docker run -v $(pwd)/data:/app/data -e SENSOR_WAL=true sensor-simulator
```

## Troubleshooting

### Database Not Being Written

1. **Check file exists:**
   ```bash
   ls -la data/sensor_data.db
   ```

2. **Check permissions:**
   ```bash
   ls -ld data/
   # Should be writable
   ```

3. **Check for errors:**
   ```bash
   tail -100 logs/sensor_simulator.log | grep -i error
   ```

4. **Enable debug logging:**
   ```bash
   LOG_LEVEL=DEBUG uv run main.py
   ```

### Database Locked Errors

If you see "database is locked" errors:

1. **Use WAL mode for better concurrency:**
   ```bash
   SENSOR_WAL=true uv run main.py
   ```

2. **Check for other processes:**
   ```bash
   lsof data/sensor_data.db
   ```

3. **Kill stuck processes:**
   ```bash
   pkill -f "sensor_data.db"
   ```

### Slow Write Performance

1. **Check batch settings in config.yaml:**
   ```yaml
   database:
     batch_size: 100  # Increase for better performance
   ```

2. **Monitor write performance:**
   ```bash
   curl http://localhost:8080/db_stats | jq '.performance'
   ```

3. **Use WAL mode for better write performance:**
   ```bash
   SENSOR_WAL=true uv run main.py
   ```

## Expected Results

When running correctly, you should see:

- **Write Rate:** ~3 readings/second (default config)
- **File Growth:** ~1-2 KB per 100 readings
- **Batch Commits:** Every 100 readings or 5 seconds
- **Anomaly Rate:** ~5% (default config)

## Performance Testing

```bash
# High-speed test (100 readings/second)
cat > test_config.yaml << EOF
simulation:
  readings_per_second: 100
  run_time_seconds: 60
database:
  batch_size: 500
EOF

# Run performance test
uv run main.py --config test_config.yaml

# Monitor performance
watch -n 1 'sqlite3 data/sensor_data.db "SELECT COUNT(*) as count, \
  printf(\"%.2f rps\", COUNT(*)/60.0) as rate FROM sensor_readings;"'
```

## Clean Up

```bash
# Remove test database
rm data/sensor_data.db

# Or preserve for analysis
mv data/sensor_data.db data/sensor_data_$(date +%Y%m%d_%H%M%S).db
```