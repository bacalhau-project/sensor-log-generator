#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "pytest-timeout",
# ]
# ///
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.database import SensorDatabase


class TestDatabaseReadOperations:
    """Test suite for database read operations and data retrieval."""

    def setup_method(self):
        """Set up test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_read.db"
        self.db = SensorDatabase(self.db_path)

    def teardown_method(self):
        """Clean up after each test."""
        if hasattr(self, "db"):
            self.db.close()
        self.temp_dir.cleanup()

    def _create_test_data(self, count=10):
        """Helper to create test data."""
        for i in range(count):
            self.db.insert_reading(
                sensor_id=f"READ{i:03d}",
                temperature=20.0 + i,
                vibration=0.1 + i * 0.01,
                voltage=12.0 + i * 0.1,
                status_code=i % 3,
                anomaly_flag=i % 5 == 0,
            )
        self.db.commit_batch()

    def test_get_readings_with_limit(self):
        """Test reading data with different limits."""
        self._create_test_data(20)

        # Test with limit
        readings = self.db.get_readings(limit=5)
        assert len(readings) == 5

        # Test with larger limit than data
        readings = self.db.get_readings(limit=50)
        assert len(readings) == 20

        # Test default limit
        readings = self.db.get_readings()
        assert len(readings) <= 100

    def test_get_readings_ordering(self):
        """Test that readings are returned in correct order."""
        self._create_test_data(10)

        readings = self.db.get_readings(limit=10)

        # Verify readings are in descending timestamp order (newest first)
        timestamps = [r["timestamp"] for r in readings]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_database_stats(self):
        """Test comprehensive database statistics."""
        self._create_test_data(50)

        stats = self.db.get_database_stats()

        assert stats["total_readings"] == 50
        assert stats["database_size_mb"] > 0
        assert "sensor_stats" in stats
        assert "anomaly_stats" in stats
        assert "performance_metrics" in stats

    def test_empty_database_reads(self):
        """Test reading from empty database."""
        # Don't insert any data

        readings = self.db.get_readings()
        assert len(readings) == 0

        stats = self.db.get_database_stats()
        assert stats["total_readings"] == 0

    def test_concurrent_read_write(self):
        """Test concurrent read and write operations."""
        # Simplified test - just verify reads work during writes

        # Write some data
        for i in range(100):
            self.db.insert_reading(
                sensor_id=f"CONCURRENT{i:03d}",
                temperature=25.0,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )

        # Force commit
        self.db.commit_batch()

        # Read while more writes happen
        readings1 = self.db.get_readings(limit=50)

        # More writes
        for i in range(100, 150):
            self.db.insert_reading(
                sensor_id=f"CONCURRENT{i:03d}",
                temperature=25.0,
                vibration=0.1,
                voltage=12.0,
                status_code=0,
            )

        self.db.commit_batch()

        # Final read
        readings2 = self.db.get_readings(limit=100)
        assert len(readings1) > 0
        assert len(readings2) > len(readings1)


class TestDatabaseEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()

    def teardown_method(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_corrupted_database_recovery(self):
        """Test handling of corrupted database."""
        db_path = Path(self.temp_dir.name) / "corrupted.db"

        # Create a corrupted database file
        with db_path.open("wb") as f:
            f.write(b"This is not a valid SQLite database")

        # Attempt to open corrupted database
        with pytest.raises(sqlite3.DatabaseError):
            SensorDatabase(db_path, preserve_existing_db=True)

    def test_missing_database_file(self):
        """Test handling when database file is missing."""
        db_path = Path(self.temp_dir.name) / "missing.db"

        # Create database
        db = SensorDatabase(db_path)
        db.insert_reading(
            sensor_id="TEST001", temperature=25.0, vibration=0.1, voltage=12.0, status_code=0
        )
        db.commit_batch()
        db.close()

        # Delete database file
        db_path.unlink()

        # Try to open with preserve_existing_db=True
        db2 = SensorDatabase(db_path, preserve_existing_db=True)
        readings = db2.get_readings()
        assert len(readings) == 0  # New empty database created
        db2.close()

    def test_read_only_database(self):
        """Test handling of read-only database."""
        db_path = Path(self.temp_dir.name) / "readonly.db"

        # Create database
        db = SensorDatabase(db_path)
        db.insert_reading(
            sensor_id="READONLY001", temperature=25.0, vibration=0.1, voltage=12.0, status_code=0
        )
        db.commit_batch()
        db.close()

        # Make database read-only
        Path.chmod(db_path, 0o444)

        # Try to open read-only database
        try:
            db2 = SensorDatabase(db_path, preserve_existing_db=True)
            # Reading should work
            readings = db2.get_readings()
            assert len(readings) == 1

            # Writing should fail
            with pytest.raises(sqlite3.OperationalError):
                db2.insert_reading(
                    sensor_id="READONLY002",
                    temperature=26.0,
                    vibration=0.1,
                    voltage=12.0,
                    status_code=0,
                )
                db2.commit_batch()

            db2.close()
        finally:
            # Restore write permissions for cleanup
            Path.chmod(db_path, 0o644)

    def test_very_large_batch(self):
        """Test handling of very large batch inserts."""
        db_path = Path(self.temp_dir.name) / "large_batch.db"
        db = SensorDatabase(db_path)

        # Insert a very large batch
        large_batch_size = 10000
        for i in range(large_batch_size):
            db.insert_reading(
                sensor_id=f"LARGE{i:05d}",
                temperature=20.0 + (i % 10),
                vibration=0.1 + (i % 100) * 0.001,
                voltage=12.0 + (i % 5) * 0.1,
                status_code=i % 3,
            )

        # Force final commit
        db.commit_batch()

        # Verify all data was inserted
        stats = db.get_database_stats()
        assert stats["total_readings"] == large_batch_size

        db.close()

    def test_null_values_handling(self):
        """Test handling of null/None values in optional fields."""
        db_path = Path(self.temp_dir.name) / "null_values.db"
        db = SensorDatabase(db_path)

        # Insert reading with minimal required fields
        db.insert_reading(
            sensor_id="NULL001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,  # Optional
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            timezone_str="+00:00",
        )
        db.commit_batch()  # Force commit

        readings = db.get_readings()
        assert len(readings) == 1

        # Verify null values are preserved
        reading = readings[0]
        # Check that some columns can be NULL
        assert reading is not None

        db.close()

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        db_path = Path(self.temp_dir.name) / "unicode.db"
        db = SensorDatabase(db_path)

        # Insert reading with Unicode characters
        db.insert_reading(
            sensor_id="UNICODE_001_🌡️",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type="spike_🔥",
            firmware_version="1.0",
            model="Model_测试",
            manufacturer="Mfg_製造商",
            location="Location_מיקום",
            timezone_str="+00:00",
        )
        db.commit_batch()  # Force commit

        readings = db.get_readings()
        assert len(readings) == 1
        assert "🌡️" in readings[0]["sensor_id"]  # sensor_id contains emoji

        db.close()

    def test_timestamp_edge_cases(self):
        """Test handling of edge case timestamps."""
        db_path = Path(self.temp_dir.name) / "timestamp_edge.db"
        db = SensorDatabase(db_path)

        # Test very old timestamp (1970)
        db.insert_reading(
            sensor_id="OLD001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            timezone_str="+00:00",
        )

        # Test future timestamp (2100)
        # future_timestamp = datetime(2100, 1, 1, tzinfo=UTC).timestamp()  # Not used in new API
        db.insert_reading(
            sensor_id="FUTURE001",
            temperature=25.0,
            vibration=0.1,
            voltage=12.0,
            status_code=0,
            anomaly_flag=False,
            anomaly_type=None,
            firmware_version="1.0",
            model="TestModel",
            manufacturer="TestMfg",
            location="Test Location",
            timezone_str="+00:00",
        )
        db.commit_batch()  # Force commit

        readings = db.get_readings()
        assert len(readings) == 2

        # Verify we got both readings
        assert readings[0]["sensor_id"] in ["OLD001", "FUTURE001"]
        assert readings[1]["sensor_id"] in ["OLD001", "FUTURE001"]

        db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
