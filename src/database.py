"""
Simple, single-threaded SQLite database for sensor readings.
No threading, no complexity, just works.
"""

import contextlib
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .safe_logger import get_safe_logger


class SensorReadingSchema(BaseModel):
    """Schema for sensor readings using Pydantic for validation."""

    timestamp: str  # ISO 8601 format
    sensor_id: str
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    vibration: float | None = None
    voltage: float | None = None
    status_code: int | None = None
    anomaly_flag: bool | None = False
    anomaly_type: str | None = None
    firmware_version: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    original_timezone: str | None = None
    # Enhanced identity fields
    serial_number: str | None = None
    manufacture_date: str | None = None
    deployment_type: str | None = None
    installation_date: str | None = None
    height_meters: float | None = None
    orientation_degrees: float | None = None
    instance_id: str | None = None
    sensor_type: str | None = None


class SensorDatabase:
    """Simple SQLite database for sensor readings."""

    def __init__(self, db_path: str, preserve_existing_db: bool = False):
        """
        Initialize the sensor database.

        Args:
            db_path: Path to the SQLite database file
            preserve_existing_db: If True, keep existing database
        """
        self.db_path = db_path
        self.logger = get_safe_logger("SensorDatabase")
        self.conn: sqlite3.Connection | None = None

        # Batch processing settings
        self.batch_buffer: list[SensorReadingSchema] = []
        self.batch_size = 50
        self.batch_timeout = 10.0
        self.last_batch_time = time.time()

        # Statistics
        self.insert_count = 0
        self.batch_insert_count = 0

        # Compatibility attributes
        self.checkpoint_on_close = True  # For test compatibility
        self.checkpoint_interval = 300  # For test compatibility

        # Handle existing database
        if not preserve_existing_db and db_path != ":memory:" and Path(db_path).exists():
            self.logger.info(f"Removing existing database at {db_path}")
            Path(db_path).unlink()
            # Remove journal files
            for suffix in ["-journal", "-wal", "-shm"]:
                journal_path = Path(str(db_path) + suffix)
                if journal_path.exists():
                    journal_path.unlink()

        # Initialize database
        self._init_db()
        self.logger.info("Database initialized successfully")

    def _init_db(self):
        """Initialize the database schema."""
        # Create database directory if needed
        if self.db_path != ":memory:":
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row

        # Set pragmas for performance
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=134217728")

        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                vibration REAL,
                voltage REAL,
                status_code INTEGER,
                anomaly_flag INTEGER DEFAULT 0,
                anomaly_type TEXT,
                firmware_version TEXT,
                model TEXT,
                manufacturer TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                original_timezone TEXT,
                serial_number TEXT,
                manufacture_date TEXT,
                deployment_type TEXT,
                installation_date TEXT,
                height_meters REAL,
                orientation_degrees REAL,
                instance_id TEXT,
                sensor_type TEXT
            )
        """)

        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_readings(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensor_id ON sensor_readings(sensor_id)")

        self.conn.commit()
        cursor.close()

    def store_reading(self, reading: SensorReadingSchema):
        """
        Store a sensor reading using the Pydantic schema.

        Args:
            reading: SensorReadingSchema object with validated data
        """
        self.batch_buffer.append(reading)

        # Check if we should commit
        current_time = time.time()
        batch_age = current_time - self.last_batch_time

        if len(self.batch_buffer) >= self.batch_size or batch_age >= self.batch_timeout:
            self.commit_batch()

    def commit_batch(self):
        """Commit the current batch to the database."""
        if not self.batch_buffer:
            return 0

        assert self.conn is not None
        cursor = self.conn.cursor()

        # Prepare data for insertion
        batch_data = []
        for reading in self.batch_buffer:
            batch_data.append(
                (
                    reading.timestamp,
                    reading.sensor_id,
                    reading.temperature,
                    reading.humidity,
                    reading.pressure,
                    reading.vibration,
                    reading.voltage,
                    reading.status_code,
                    1 if reading.anomaly_flag else 0,
                    reading.anomaly_type,
                    reading.firmware_version,
                    reading.model,
                    reading.manufacturer,
                    reading.location,
                    reading.latitude,
                    reading.longitude,
                    reading.original_timezone,
                    reading.serial_number,
                    reading.manufacture_date,
                    reading.deployment_type,
                    reading.installation_date,
                    reading.height_meters,
                    reading.orientation_degrees,
                    reading.instance_id,
                    reading.sensor_type,
                )
            )

        # Insert batch
        cursor.executemany(
            """
            INSERT INTO sensor_readings (
                timestamp, sensor_id, temperature, humidity, pressure,
                vibration, voltage, status_code, anomaly_flag, anomaly_type,
                firmware_version, model, manufacturer, location,
                latitude, longitude, original_timezone,
                serial_number, manufacture_date, deployment_type,
                installation_date, height_meters, orientation_degrees,
                instance_id, sensor_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            batch_data,
        )

        assert self.conn is not None
        self.conn.commit()

        count = len(self.batch_buffer)
        self.insert_count += count
        self.batch_insert_count += 1

        # Clear buffer and reset timer
        self.batch_buffer.clear()
        self.last_batch_time = time.time()

        cursor.close()
        return count

    def insert_reading(
        self,
        sensor_id: str,
        temperature: float,
        vibration: float,
        voltage: float,
        status_code: int,
        anomaly_flag: bool = False,
        anomaly_type: str | None = None,
        **kwargs,
    ):
        """
        Legacy method for backward compatibility with tests.
        """
        reading = SensorReadingSchema(
            timestamp=datetime.now(UTC).isoformat(),
            sensor_id=sensor_id,
            temperature=temperature,
            vibration=vibration,
            voltage=voltage,
            status_code=status_code,
            anomaly_flag=anomaly_flag,
            anomaly_type=anomaly_type,
            **kwargs,
        )
        self.store_reading(reading)

    def get_readings(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get readings from the database."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM sensor_readings
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        readings = []
        for row in cursor.fetchall():
            readings.append(dict(row))

        cursor.close()
        return readings

    def get_reading_stats(self) -> dict:
        """Get basic statistics."""
        assert self.conn is not None
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        total = cursor.fetchone()[0]

        cursor.close()

        return {
            "total_readings": total,
        }

    def get_database_stats(self) -> dict[str, Any]:
        """Get comprehensive database statistics."""
        stats = self.get_reading_stats()

        # Add file size if not in-memory
        if self.db_path != ":memory:" and Path(self.db_path).exists():
            stats["database_size_bytes"] = Path(self.db_path).stat().st_size
            stats["database_size_mb"] = stats["database_size_bytes"] / (1024 * 1024)
        else:
            stats["database_size_bytes"] = 0
            stats["database_size_mb"] = 0

        # Add placeholders for expected fields
        stats["sensor_stats"] = {}
        stats["anomaly_stats"] = {}

        # Add performance metrics for compatibility
        stats["performance_metrics"] = {
            "total_batches": self.batch_insert_count,
            "total_inserts": self.insert_count,
            "avg_batch_size": self.insert_count / max(1, self.batch_insert_count),
            "avg_insert_time_ms": 0,  # Not tracked in simple version
        }

        return stats

    def is_healthy(self) -> bool:
        """Check if database is healthy."""
        try:
            assert self.conn is not None
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            return result is not None and result[0] == 1
        except Exception:
            return False

    def close(self):
        """Close the database connection."""
        # Commit any pending data (skip if read-only database)
        if self.batch_buffer:
            try:
                self.commit_batch()
            except sqlite3.OperationalError as e:
                if "readonly database" not in str(e):
                    raise
                # Ignore read-only errors on close

        # Close connection
        if self.conn:
            self.conn.close()
            self.conn = None

        self.logger.info("Database closed")

    def __del__(self):
        """Cleanup on deletion."""
        with contextlib.suppress(Exception):
            self.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # Compatibility method
    def stop_background_commit_thread(self):
        """No-op for compatibility."""
        pass
