#!/usr/bin/env python3
# /// script
# dependencies = ["tabulate"]
# ///
"""Test reading database while simulator is writing."""

import sqlite3
import time
import sys
from tabulate import tabulate


def main():
    db_path = "data/sensor_data.db"

    print("=== External Database Reader Test ===")
    print("This simulates an external process reading the database")
    print("while the simulator is actively writing.\n")

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)

        # Check journal mode
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        print(f"📝 Journal Mode: {mode.upper()}")

        if mode.upper() == "WAL":
            print("✅ WAL mode - concurrent reads should work smoothly!\n")
        else:
            print("⚠️  DELETE mode - may experience brief locks during writes\n")

        # Read data every second for 10 iterations
        for i in range(10):
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    MAX(timestamp) as latest,
                    AVG(temperature) as avg_temp,
                    SUM(anomaly_flag) as anomalies
                FROM sensor_readings
            """)

            row = cursor.fetchone()
            total, latest, avg_temp, anomalies = row

            # Get last 3 readings
            cursor.execute("""
                SELECT 
                    datetime(timestamp, 'localtime') as time,
                    sensor_id,
                    printf('%.1f°C', temperature) as temp,
                    CASE WHEN anomaly_flag = 1 THEN '⚠️' ELSE '✓' END as status
                FROM sensor_readings 
                ORDER BY timestamp DESC 
                LIMIT 3
            """)

            recent = cursor.fetchall()

            # Clear screen for clean output
            if i > 0:
                print("\033[H\033[J", end="")  # Clear screen

            print(f"=== Reading #{i + 1} at {time.strftime('%H:%M:%S')} ===\n")
            print(f"📊 Total Records: {total}")
            print(f"🌡️  Avg Temperature: {avg_temp:.1f}°C")
            print(f"⚠️  Anomalies: {anomalies or 0}")
            print(f"⏰ Latest: {latest}\n")

            if recent:
                print("📈 Recent Readings:")
                headers = ["Time", "Sensor", "Temp", "Status"]
                print(tabulate(recent, headers=headers, tablefmt="simple"))

            time.sleep(1)

        cursor.close()
        conn.close()

        print("\n✅ External reader test completed successfully!")

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print(f"❌ Database locked! This can happen in DELETE mode.")
            print("   Try setting SENSOR_WAL=true for better concurrency.")
        else:
            print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
