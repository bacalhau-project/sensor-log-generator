# Monitoring Scripts

This directory contains scripts for monitoring database and system health.

## Scripts

- **monitor_db.sh** - Monitors database size, connections, and performance
- **check_db.sh** - Checks database integrity and health
- **query_all_log_files.sh** - Queries and analyzes all log files

## Usage Examples

```bash
# Monitor database in real-time
./scripts/monitoring/monitor_db.sh

# Check database health
./scripts/monitoring/check_db.sh

# Query all logs
./scripts/monitoring/query_all_log_files.sh
```

## Notes

These scripts are designed to run continuously or periodically to ensure system health.
