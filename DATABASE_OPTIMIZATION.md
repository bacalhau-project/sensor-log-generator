# Database Optimization for Concurrent Reading

## Changes Made for Better Read Concurrency

### 1. Write Batching Optimizations
- **Batch size**: Increased from 20 to 50 records
- **Commit interval**: Increased from 5s to 10s
- **Checkpoint interval**: Increased from 5s to 10s
- **Result**: Fewer write operations = fewer read conflicts

### 2. Safe Reading Implementation

All monitoring scripts now use read-only mode:
```bash
sqlite3 "file:data/sensor_data.db?mode=ro" "SELECT ..."
```

This prevents:
- "database is locked" errors
- "file is not a database" errors during checkpoints
- Accidental writes from read operations

### 3. Documentation & Examples

Added comprehensive examples in the README for safe reading in:
- **Bash**: One-liner monitoring scripts with error handling
- **Python**: Context managers with retry logic
- **JavaScript**: Both callback and async/await patterns

### 4. Provided Tools

- `read_safe.py`: Simple example of safe reading with monitoring mode
- `monitor_db.sh`: Updated to use read-only connections
- `check_db.sh`: Updated to use read-only connections

## Performance Impact

With these optimizations:
- **Write performance**: Slightly improved due to larger batches
- **Read reliability**: Greatly improved - minimal conflicts
- **Checkpoint frequency**: Reduced from ~12/min to ~6/min
- **Read windows**: Consistent 10-second windows between commits

## Best Practices for External Readers

1. **Always use read-only mode**:
   ```bash
   sqlite3 "file:path/to/db?mode=ro"
   ```

2. **Set appropriate timeouts**:
   ```python
   conn = sqlite3.connect(db_path, timeout=30.0)
   ```

3. **Handle transient errors gracefully**:
   ```python
   except sqlite3.OperationalError as e:
       if "database is locked" in str(e):
           time.sleep(0.5)
           retry()
   ```

4. **Don't hold connections open**:
   ```python
   with get_connection() as conn:
       # Quick query
       result = conn.execute(query).fetchall()
   # Connection auto-closed
   ```

## Monitoring Performance

To verify the optimizations are working:

```bash
# Watch for checkpoint operations (should be ~6/minute)
while true; do
    echo "[$(date '+%H:%M:%S')] WAL size: $(ls -lh data/sensor_data.db-wal 2>/dev/null | awk '{print $5}')"
    sleep 10
done
```

## Troubleshooting

If you still experience read issues:

1. **Check WAL mode is active**:
   ```bash
   sqlite3 data/sensor_data.db "PRAGMA journal_mode;"
   ```

2. **Verify checkpoint frequency**:
   Look for "checkpoint" in logs

3. **Ensure read-only mode**:
   Always use `file:` URI syntax with `?mode=ro`

## Result

The database is now optimized for:
- ✅ Multiple concurrent readers
- ✅ Continuous writing without blocking reads
- ✅ Minimal "database locked" errors
- ✅ Consistent read windows every 10 seconds