#!/usr/bin/env python3
"""
Safe reading examples for the sensor database.
This script shows various ways to safely read from the database while the sensor is writing.

IMPORTANT: Always use read-only mode to prevent corruption!
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path


class SafeSensorReader:
    """
    Safe reader for sensor database that won't cause corruption.
    Always uses read-only connections.
    """

    def __init__(self, db_path: str = "data/sensor_data.db"):
        """Initialize the reader with database path."""
        self.db_path = db_path

        # Check if database exists
        if not Path(db_path).exists():
            print(f"❌ Database not found: {db_path}")
            print("Please run the sensor simulator first to create the database")
            exit(1)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a read-only connection to the database.

        CRITICAL: This uses mode=ro to ensure read-only access!
        """
        # ✅ CORRECT: Read-only connection
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def get_record_count(self) -> int:
        """Get total number of records in the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_latest_readings(self, limit: int = 10) -> list:
        """Get the most recent sensor readings."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                timestamp,
                sensor_id,
                temperature,
                humidity,
                pressure,
                voltage,
                anomaly_flag,
                anomaly_type
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
        """,
            (limit,),
        )

        readings = []
        for row in cursor.fetchall():
            readings.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "sensor_id": row["sensor_id"],
                    "temperature": row["temperature"],
                    "humidity": row["humidity"],
                    "pressure": row["pressure"],
                    "voltage": row["voltage"],
                    "anomaly": bool(row["anomaly_flag"]),
                    "anomaly_type": row["anomaly_type"],
                }
            )

        conn.close()
        return readings

    def get_readings_by_time_range(self, hours_ago: int = 1) -> list:
        """Get readings from the last N hours."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_ago)

        cursor.execute(
            """
            SELECT * FROM sensor_readings
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        """,
            (start_time.isoformat(), end_time.isoformat()),
        )

        readings = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return readings

    def get_anomalies(self, limit: int = 20) -> list:
        """Get recent anomalies from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                timestamp,
                sensor_id,
                temperature,
                anomaly_type
            FROM sensor_readings
            WHERE anomaly_flag = 1
            ORDER BY id DESC
            LIMIT ?
        """,
            (limit,),
        )

        anomalies = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return anomalies

    def get_statistics(self) -> dict:
        """Get statistical summary of the sensor data."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_readings,
                COUNT(DISTINCT sensor_id) as unique_sensors,
                MIN(timestamp) as first_reading,
                MAX(timestamp) as last_reading,
                AVG(temperature) as avg_temperature,
                MIN(temperature) as min_temperature,
                MAX(temperature) as max_temperature,
                AVG(humidity) as avg_humidity,
                AVG(pressure) as avg_pressure,
                SUM(anomaly_flag) as total_anomalies
            FROM sensor_readings
        """)

        stats = dict(cursor.fetchone())

        # Calculate anomaly rate
        if stats["total_readings"] > 0:
            stats["anomaly_rate"] = stats["total_anomalies"] / stats["total_readings"]
        else:
            stats["anomaly_rate"] = 0

        conn.close()
        return stats

    def monitor_growth(self, duration: int = 10):
        """
        Monitor database growth for a specified duration.
        Shows how fast data is being written.
        """
        print(f"\n📊 Monitoring database growth for {duration} seconds...")

        initial_count = self.get_record_count()
        start_time = time.time()

        while time.time() - start_time < duration:
            time.sleep(1)
            current_count = self.get_record_count()
            rate = (current_count - initial_count) / (time.time() - start_time)
            print(f"Records: {current_count:,} | Growth rate: {rate:.1f} records/sec", end="\r")

        final_count = self.get_record_count()
        total_added = final_count - initial_count
        avg_rate = total_added / duration

        print(
            f"\n✅ Added {total_added} records in {duration} seconds ({avg_rate:.1f} records/sec)"
        )

    def continuous_monitoring(self, interval: int = 5):
        """
        Continuously monitor the database (Ctrl+C to stop).
        Useful for watching a running sensor simulator.
        """
        print(f"\n🔄 Continuous monitoring (interval: {interval}s, Ctrl+C to stop)")
        print("-" * 60)

        try:
            while True:
                count = self.get_record_count()
                latest = self.get_latest_readings(1)

                if latest:
                    reading = latest[0]
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Records: {count:,} | "
                        f"Latest: {reading['sensor_id']} | "
                        f"Temp: {reading['temperature']:.1f}°C | "
                        f"Anomaly: {'Yes' if reading['anomaly'] else 'No'}"
                    )

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n✋ Monitoring stopped")


def main():
    """Main function showing various reading examples."""
    print("🌡️ Sensor Database Reader - Safe Reading Examples")
    print("=" * 60)

    # Create reader
    reader = SafeSensorReader()

    # 1. Get basic count
    count = reader.get_record_count()
    print("\n📊 Database Statistics:")
    print(f"  Total records: {count:,}")

    # 2. Get overall statistics
    stats = reader.get_statistics()
    if stats["total_readings"] > 0:
        print(f"  Date range: {stats['first_reading'][:19]} to {stats['last_reading'][:19]}")
        print(f"  Unique sensors: {stats['unique_sensors']}")
        print(
            f"  Temperature range: {stats['min_temperature']:.1f}°C to {stats['max_temperature']:.1f}°C"
        )
        print(f"  Average temperature: {stats['avg_temperature']:.1f}°C")
        print(f"  Total anomalies: {stats['total_anomalies']}")
        print(f"  Anomaly rate: {stats['anomaly_rate'] * 100:.2f}%")

    # 3. Show latest readings
    print("\n📖 Latest 5 Readings:")
    latest = reader.get_latest_readings(5)
    for reading in latest:
        anomaly_info = f" [🔴 {reading['anomaly_type']}]" if reading["anomaly"] else ""
        print(
            f"  {reading['timestamp'][:19]} | {reading['sensor_id']} | "
            f"{reading['temperature']:.1f}°C | {reading['humidity']:.1f}%{anomaly_info}"
        )

    # 4. Show recent anomalies
    print("\n⚠️ Recent Anomalies:")
    anomalies = reader.get_anomalies(5)
    if anomalies:
        for anomaly in anomalies:
            print(
                f"  {anomaly['timestamp'][:19]} | {anomaly['sensor_id']} | "
                f"{anomaly['anomaly_type']} | {anomaly['temperature']:.1f}°C"
            )
    else:
        print("  No anomalies found")

    # 5. Offer monitoring options
    print("\n🔧 Monitoring Options:")
    print("  1. Monitor growth for 10 seconds")
    print("  2. Continuous monitoring (Ctrl+C to stop)")
    print("  3. Exit")

    try:
        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            reader.monitor_growth(duration=10)
        elif choice == "2":
            reader.continuous_monitoring(interval=2)
        else:
            print("👋 Goodbye!")

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
