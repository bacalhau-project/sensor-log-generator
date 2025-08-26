"""
Simple, single-threaded SQLite database for sensor readings.
No threading, no complexity, just works.
"""

import contextlib
import sqlite3
import time
from pathlib import Path

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
        self.batch_buffer: list[tuple] = []  # List of tuples for SQL insertion
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
        # Convert Pydantic model to tuple for SQL insertion
        reading_tuple = (
            reading.timestamp,
            reading.sensor_id,
            reading.temperature,
            reading.humidity,
            reading.pressure,
            reading.voltage,
            reading.vibration,
            reading.status_code,
            reading.anomaly_flag,
            reading.anomaly_type,
            reading.firmware_version,
            reading.model,
            reading.manufacturer,
            reading.serial_number,
            reading.location,
            reading.latitude,
            reading.longitude,
            reading.original_timezone,  # Fixed: was timezone
            reading.deployment_type,
            reading.installation_date,
            reading.height_meters,
        )
        self.batch_buffer.append(reading_tuple)

        # Check if we should commit
        current_time = time.time()
        batch_age = current_time - self.last_batch_time

        if len(self.batch_buffer) >= self.batch_size or batch_age >= self.batch_timeout:
            self.commit_batch()

    def commit_batch(self):
        """Commit the current batch of readings to the database."""
        if not self.batch_buffer:
            return

        try:
            # Use executemany for efficient bulk insert
            self.conn.executemany(
                """
                INSERT INTO sensor_readings (
                    timestamp, sensor_id, temperature, humidity, pressure,
                    voltage, vibration, status_code, anomaly_flag, anomaly_type,
                    firmware_version, model, manufacturer, serial_number,
                    location, latitude, longitude, original_timezone,
                    deployment_type, installation_date, height_meters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self.batch_buffer,
            )
            self.conn.commit()

            # Checkpoint WAL periodically for Docker volume sync
            # Do this every 10 commits (roughly every 100 seconds)
            if not hasattr(self, "_commit_count"):
                self._commit_count = 0
            self._commit_count += 1

            if self._commit_count % 10 == 0:
                try:
                    self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    self.logger.debug(f"WAL checkpoint at commit {self._commit_count}")
                except Exception as e:
                    self.logger.warning(f"Periodic WAL checkpoint failed: {e}")

            # Clear the buffer
            self.batch_buffer = []
            self.last_commit_time = time.time()

        except sqlite3.Error as e:
            self.logger.error(f"Failed to commit batch: {e}")
            raise
            # Ignore read-only errors on close

        # Checkpoint WAL to ensure data is written to main database file
        # This is critical for Docker volumes on macOS
        try:
            if hasattr(self, "conn") and self.conn:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.logger.info("WAL checkpoint completed")
        except Exception as e:
            self.logger.warning(f"WAL checkpoint failed: {e}")

        # Close connection
        if self.conn:
            self.conn.close()
            self.conn = None

        self.logger.info("Database closed")

    def close(self):
        """Close the database connection properly."""
        # Commit any pending data
        if self.batch_buffer:
            try:
                self.commit_batch()
            except sqlite3.OperationalError as e:
                if "readonly database" not in str(e):
                    raise

        # Checkpoint WAL to ensure data is written to main database file
        # This is critical for Docker volumes on macOS/Windows
        try:
            if hasattr(self, "conn") and self.conn:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.logger.info("WAL checkpoint completed on close")
        except Exception as e:
            self.logger.warning(f"WAL checkpoint failed: {e}")

        # Close the connection
        if hasattr(self, "conn") and self.conn:
            self.conn.close()
            self.conn = None
            self.logger.info("Database connection closed")

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

    # Compatibility methods
    def stop_background_commit_thread(self):
        """No-op for compatibility."""
        pass

    def get_database_stats(self) -> dict:
        """Get database statistics."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sensor_readings WHERE anomaly_flag = 1")
            anomalies = cursor.fetchone()[0]

            return {
                "total_readings": total,
                "anomaly_count": anomalies,
                "database_size": 0,  # Not calculated for simplicity
            }
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            return {"total_readings": 0, "anomaly_count": 0, "database_size": 0}
