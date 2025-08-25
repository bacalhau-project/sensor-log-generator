#!/usr/bin/env python3
"""
Simple example of reading from the sensor database safely.
This script demonstrates best practices for concurrent reading.
"""

import sqlite3
import time
from pathlib import Path


def safe_read(db_path="data/sensor_data.db", query=None):
    """
    Safely read from the database using read-only mode.

    Args:
        db_path: Path to the database file
        query: SQL query to execute (default: count readings)

    Returns:
        Query result or None if error
    """
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return None

    if query is None:
        query = "SELECT COUNT(*) as count FROM sensor_readings"

    try:
        # Open in read-only mode with URI syntax
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            timeout=5.0,  # 5 second timeout
        )

        # Set to query-only for extra safety
        conn.execute("PRAGMA query_only=1;")

        # Execute query
        cursor = conn.cursor()
        result = cursor.execute(query).fetchall()

        conn.close()
        return result

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            return "Database busy (normal during writes)"
        elif "file is not a database" in str(e):
            return "Database updating (checkpoint in progress)"
        else:
            return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


def monitor_loop(interval=2):
    """Monitor the database with safe reading."""
    print("Monitoring database (Ctrl+C to stop)...")
    print("-" * 40)

    prev_count = 0

    while True:
        result = safe_read()
        timestamp = time.strftime("%H:%M:%S")

        if isinstance(result, list) and result:
            count = result[0][0]
            diff = count - prev_count if prev_count > 0 else 0
            print(f"[{timestamp}] Readings: {count:,} (+{diff})")
            prev_count = count
        else:
            print(f"[{timestamp}] {result}")

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


def main():
    """Main function with examples."""
    import argparse

    parser = argparse.ArgumentParser(description="Safe database reader example")
    parser.add_argument("--monitor", action="store_true", help="Monitor continuously")
    parser.add_argument("--query", type=str, help="Custom SQL query")
    parser.add_argument("--interval", type=int, default=2, help="Monitor interval (seconds)")

    args = parser.parse_args()

    if args.monitor:
        monitor_loop(args.interval)
    else:
        # Single query
        query = (
            args.query
            or """
            SELECT 
                COUNT(*) as total_readings,
                COUNT(DISTINCT sensor_id) as sensors,
                MAX(timestamp) as latest,
                SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) as anomalies
            FROM sensor_readings
        """
        )

        result = safe_read(query=query)

        if isinstance(result, list) and result:
            if args.query:
                # Custom query - just print results
                for row in result:
                    print(row)
            else:
                # Default summary query
                row = result[0]
                print(f"Total readings: {row[0]:,}")
                print(f"Sensors: {row[1]}")
                print(f"Latest: {row[2]}")
                print(f"Anomalies: {row[3]}")
        else:
            print(result)


if __name__ == "__main__":
    main()
