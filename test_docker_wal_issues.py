#!/usr/bin/env python3
# /// script
# dependencies = ["docker", "tabulate", "psutil"]
# ///
"""
Comprehensive test to identify WAL mode issues in Docker containers.
Tests various scenarios where WAL mode might fail.
"""

import os
import time
import sqlite3
import subprocess
import tempfile
from pathlib import Path
import docker
from tabulate import tabulate
import json


class DockerWALTester:
    def __init__(self):
        self.client = docker.from_env()
        self.test_results = []
        self.test_dir = Path("docker_wal_tests")
        self.test_dir.mkdir(exist_ok=True)

    def cleanup(self):
        """Clean up test containers and files."""
        print("🧹 Cleaning up...")
        # Stop and remove containers
        for container in self.client.containers.list(all=True):
            if container.name and "wal-test" in container.name:
                try:
                    container.stop()
                    container.remove()
                except:
                    pass

        # Remove test volumes
        for volume in self.client.volumes.list():
            if "wal-test" in volume.name:
                try:
                    volume.remove()
                except:
                    pass

    def run_test(self, test_name, test_func):
        """Run a single test and record results."""
        print(f"\n🧪 Testing: {test_name}")
        print("=" * 60)

        try:
            result = test_func()
            self.test_results.append(
                {
                    "Test": test_name,
                    "Status": "✅ PASS" if result["success"] else "❌ FAIL",
                    "Details": result["message"],
                    "Mode": result.get("mode", "N/A"),
                }
            )
            return result["success"]
        except Exception as e:
            self.test_results.append(
                {"Test": test_name, "Status": "❌ ERROR", "Details": str(e), "Mode": "N/A"}
            )
            return False

    def test_basic_wal_mode(self):
        """Test basic WAL mode functionality in container."""
        test_path = self.test_dir / "basic_wal"
        test_path.mkdir(exist_ok=True)

        # Build and run container with WAL mode
        container = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-basic",
            environment={"SENSOR_WAL": "true", "LOG_LEVEL": "INFO"},
            volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "rw"}},
            remove=False,
        )

        time.sleep(10)

        # Check database from host
        db_path = test_path / "sensor_data.db"

        if not db_path.exists():
            container.stop()
            container.remove()
            return {"success": False, "message": "Database file not created"}

        # Check journal mode
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]

        # Check for WAL files
        wal_exists = (test_path / "sensor_data.db-wal").exists()
        shm_exists = (test_path / "sensor_data.db-shm").exists()

        # Count records
        cursor.execute("SELECT COUNT(*) FROM sensor_readings;")
        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        container.stop()
        container.remove()

        success = mode.lower() == "wal" and count > 0
        message = f"Mode: {mode}, Records: {count}, WAL file: {wal_exists}, SHM file: {shm_exists}"

        return {"success": success, "message": message, "mode": mode}

    def test_cross_boundary_access(self):
        """Test reading from host while container writes in WAL mode."""
        test_path = self.test_dir / "cross_boundary"
        test_path.mkdir(exist_ok=True)

        # Start container in WAL mode
        container = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-boundary",
            environment={"SENSOR_WAL": "true"},
            volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "rw"}},
            remove=False,
        )

        time.sleep(5)

        # Try to read from host multiple times
        db_path = test_path / "sensor_data.db"
        errors = []
        counts = []

        for i in range(5):
            try:
                conn = sqlite3.connect(str(db_path), timeout=1.0)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sensor_readings;")
                count = cursor.fetchone()[0]
                counts.append(count)
                cursor.close()
                conn.close()
                time.sleep(1)
            except sqlite3.OperationalError as e:
                errors.append(str(e))

        container.stop()
        container.remove()

        success = len(errors) == 0 and len(counts) > 0
        message = f"Successful reads: {len(counts)}/5, Errors: {len(errors)}"
        if errors:
            message += f" - {errors[0]}"

        return {"success": success, "message": message}

    def test_concurrent_containers(self):
        """Test multiple containers accessing same database."""
        test_path = self.test_dir / "concurrent"
        test_path.mkdir(exist_ok=True)

        # Start writer container in WAL mode
        writer = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-writer",
            environment={"SENSOR_WAL": "true"},
            volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "rw"}},
            remove=False,
        )

        time.sleep(5)

        # Start reader container
        reader = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-reader",
            command='bash -c "while true; do sqlite3 /app/data/sensor_data.db \\"SELECT COUNT(*) FROM sensor_readings;\\"; sleep 2; done"',
            volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "ro"}},
            remove=False,
        )

        time.sleep(10)

        # Check reader logs for errors
        reader_logs = reader.logs(tail=10).decode()
        has_errors = "error" in reader_logs.lower() or "locked" in reader_logs.lower()

        # Get final count
        db_path = test_path / "sensor_data.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        writer.stop()
        reader.stop()
        writer.remove()
        reader.remove()

        success = not has_errors and count > 0
        message = f"Records: {count}, Reader errors: {has_errors}"

        return {"success": success, "message": message}

    def test_storage_drivers(self):
        """Test WAL mode with different storage scenarios."""
        results = []

        # Test with named volume (Docker managed)
        volume = self.client.volumes.create(name="wal-test-volume")

        container = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-volume",
            environment={"SENSOR_WAL": "true"},
            volumes={"wal-test-volume": {"bind": "/app/data", "mode": "rw"}},
            remove=False,
        )

        time.sleep(10)

        # Check if data was written
        exec_result = container.exec_run(
            "sqlite3 /app/data/sensor_data.db 'SELECT COUNT(*) FROM sensor_readings;'"
        )
        volume_success = exec_result.exit_code == 0 and int(exec_result.output.decode().strip()) > 0

        container.stop()
        container.remove()
        volume.remove()

        message = "Named volume: " + ("✅ Works" if volume_success else "❌ Failed")

        return {"success": volume_success, "message": message}

    def test_file_permissions(self):
        """Test WAL mode with different file permissions."""
        test_path = self.test_dir / "permissions"
        test_path.mkdir(exist_ok=True)

        # Create database with restricted permissions
        os.chmod(test_path, 0o755)

        container = self.client.containers.run(
            "sensor-simulator",
            detach=True,
            name="wal-test-perms",
            environment={"SENSOR_WAL": "true"},
            volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "rw"}},
            remove=False,
        )

        time.sleep(10)

        # Check database
        db_path = test_path / "sensor_data.db"
        success = False
        message = "No database created"

        if db_path.exists():
            # Check file permissions
            stat_info = os.stat(db_path)
            perms = oct(stat_info.st_mode)[-3:]

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_readings;")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            success = count > 0
            message = f"Permissions: {perms}, Records: {count}"

        container.stop()
        container.remove()

        return {"success": success, "message": message}

    def test_delete_mode_comparison(self):
        """Compare DELETE mode vs WAL mode in Docker."""
        results = {}

        for mode, env in [("DELETE", {}), ("WAL", {"SENSOR_WAL": "true"})]:
            test_path = self.test_dir / f"compare_{mode.lower()}"
            test_path.mkdir(exist_ok=True)

            container = self.client.containers.run(
                "sensor-simulator",
                detach=True,
                name=f"wal-test-compare-{mode.lower()}",
                environment=env,
                volumes={str(test_path.absolute()): {"bind": "/app/data", "mode": "rw"}},
                remove=False,
            )

            time.sleep(10)

            # Test concurrent read
            db_path = test_path / "sensor_data.db"
            read_errors = 0

            for _ in range(5):
                try:
                    conn = sqlite3.connect(str(db_path), timeout=0.5)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sensor_readings;")
                    cursor.close()
                    conn.close()
                except:
                    read_errors += 1
                time.sleep(0.5)

            container.stop()
            container.remove()

            results[mode] = read_errors

        success = True  # Comparison test always succeeds
        message = f"Lock errors - DELETE: {results['DELETE']}/5, WAL: {results['WAL']}/5"

        return {"success": success, "message": message}

    def run_all_tests(self):
        """Run all tests and generate report."""
        print("🚀 Starting Docker WAL Mode Tests")
        print("=" * 60)

        # Ensure Docker image is built
        print("📦 Building Docker image...")
        subprocess.run(
            ["docker", "build", "-t", "sensor-simulator", "."], capture_output=True, check=True
        )

        self.cleanup()

        # Run tests
        tests = [
            ("Basic WAL Mode", self.test_basic_wal_mode),
            ("Cross-Boundary Access", self.test_cross_boundary_access),
            ("Concurrent Containers", self.test_concurrent_containers),
            ("Storage Drivers", self.test_storage_drivers),
            ("File Permissions", self.test_file_permissions),
            ("Mode Comparison", self.test_delete_mode_comparison),
        ]

        for test_name, test_func in tests:
            self.run_test(test_name, test_func)

        # Generate report
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS")
        print("=" * 80)

        print(tabulate(self.test_results, headers="keys", tablefmt="grid"))

        # Summary
        passed = sum(1 for r in self.test_results if "PASS" in r["Status"])
        failed = sum(1 for r in self.test_results if "FAIL" in r["Status"])
        errors = sum(1 for r in self.test_results if "ERROR" in r["Status"])

        print(f"\n📈 Summary: {passed} passed, {failed} failed, {errors} errors")

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 40)

        if any("FAIL" in r["Status"] for r in self.test_results if "Cross-Boundary" in r["Test"]):
            print("⚠️  WAL mode has issues with cross-boundary access")
            print("   → Use DELETE mode (default) for Docker volumes")

        if any("FAIL" in r["Status"] for r in self.test_results if "Concurrent" in r["Test"]):
            print("⚠️  Concurrent access issues detected")
            print("   → Consider using separate databases or DELETE mode")

        print("\n✅ Best Practice: Use DELETE mode (default) for Docker")
        print("   It provides better compatibility with volume mounts")

        self.cleanup()

        return passed > 0


if __name__ == "__main__":
    tester = DockerWALTester()
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted")
        tester.cleanup()
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        tester.cleanup()
        raise
