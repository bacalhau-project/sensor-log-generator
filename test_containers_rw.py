#!/usr/bin/env -S uv run python
"""
Test concurrent database read/write using Docker containers.

This script spawns multiple Docker containers:
- One writer container that writes sensor data
- Multiple reader containers that read from the same database

This tests SQLite WAL mode behavior across container boundaries.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import click
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class ContainerOrchestrator:
    """Orchestrate reader and writer containers for database testing."""

    def __init__(
        self,
        db_path: str,
        num_readers: int,
        test_duration: int,
        write_rate: int = 10,
        read_interval: float = 0.5,
    ):
        self.db_path = Path(db_path).resolve()
        self.num_readers = num_readers
        self.test_duration = test_duration
        self.write_rate = write_rate
        self.read_interval = read_interval
        self.containers: list[str] = []
        self.reader_stats: dict[int, dict] = {}
        self.writer_stats: dict = {}

        # Image names
        self.reader_image = "sensor-reader-test"
        self.writer_image = "sensor-writer-test"

    def build_images(self) -> bool:
        """Build Docker images for reader and writer containers."""
        console.print("[blue]🔨 Building container images...[/blue]")

        # Build reader image
        if not self._build_reader_image():
            return False

        # Build writer image
        return self._build_writer_image()

    def _build_reader_image(self) -> bool:
        """Build the reader container image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            script_path = Path(tmpdir) / "reader.py"

            # Reader script
            reader_script = '''#!/usr/bin/env python3
import sqlite3
import json
import sys
import time
from datetime import datetime

def read_database(db_path, container_id, duration, interval):
    start_time = time.time()
    stats = {
        "container_id": container_id,
        "type": "reader",
        "reads": 0,
        "errors": 0,
        "total_records": 0,
        "latest_record": None,
        "read_times": []
    }

    while time.time() - start_time < duration:
        try:
            read_start = time.time()

            # Connect read-only with WAL mode
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA journal_mode = WAL")

            cursor = conn.cursor()

            # Various read operations
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            count = cursor.fetchone()[0]
            stats["total_records"] = count

            # Get latest record
            cursor.execute("""
                SELECT id, timestamp, sensor_id, temperature
                FROM sensor_readings
                ORDER BY id DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()
            if latest:
                stats["latest_record"] = {
                    "id": latest[0],
                    "timestamp": latest[1],
                    "temperature": latest[3]
                }

            # Random reads
            if count > 0:
                cursor.execute("""
                    SELECT AVG(temperature), MIN(temperature), MAX(temperature)
                    FROM sensor_readings
                    WHERE id > ?
                """, (max(0, count - 100),))
                cursor.fetchone()

            conn.close()

            read_time = time.time() - read_start
            stats["read_times"].append(read_time)
            stats["reads"] += 1

            print(json.dumps(stats), flush=True)

        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = str(e)
            print(json.dumps(stats), flush=True)

        time.sleep(interval)

    stats["final"] = True
    if stats["read_times"]:
        stats["avg_read_time"] = sum(stats["read_times"]) / len(stats["read_times"])
    print(json.dumps(stats), flush=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    read_database(args.db_path, args.container_id, args.duration, args.interval)
'''

            # Dockerfile
            dockerfile = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*
COPY reader.py /app/reader.py
WORKDIR /app
ENTRYPOINT ["python", "/app/reader.py"]
"""

            dockerfile_path.write_text(dockerfile)
            script_path.write_text(reader_script)

            try:
                subprocess.run(
                    ["docker", "build", "-t", self.reader_image, tmpdir],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                console.print(f"[green]✓ Built reader image: {self.reader_image}[/green]")
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ Failed to build reader: {e.stderr}[/red]")
                return False

    def _build_writer_image(self) -> bool:
        """Build the writer container image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            script_path = Path(tmpdir) / "writer.py"

            # Writer script
            writer_script = '''#!/usr/bin/env python3
import sqlite3
import json
import time
import random
from datetime import datetime, UTC

def write_database(db_path, duration, write_rate):
    start_time = time.time()
    stats = {
        "type": "writer",
        "writes": 0,
        "errors": 0,
        "batches": 0,
        "write_times": []
    }

    # Initialize database if needed
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")

    cursor = conn.cursor()
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
            anomaly_flag INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    batch = []
    batch_size = 10
    last_batch_time = time.time()

    while time.time() - start_time < duration:
        try:
            # Generate sensor data
            timestamp = datetime.now(UTC).isoformat()
            sensor_id = f"CONTAINER_SENSOR_{random.randint(1, 5):03d}"
            temperature = 20.0 + random.gauss(0, 2)
            humidity = 65.0 + random.gauss(0, 5)
            pressure = 1013.25 + random.gauss(0, 10)
            vibration = random.uniform(0.1, 0.5)
            voltage = 12.0 + random.gauss(0, 0.1)
            status_code = 0 if random.random() > 0.05 else random.randint(1, 5)
            anomaly_flag = 1 if random.random() < 0.02 else 0

            reading = (
                timestamp, sensor_id, temperature, humidity, pressure,
                vibration, voltage, status_code, anomaly_flag
            )

            batch.append(reading)

            # Write batch if needed
            if len(batch) >= batch_size or time.time() - last_batch_time > 1.0:
                write_start = time.time()

                cursor.executemany("""
                    INSERT INTO sensor_readings
                    (timestamp, sensor_id, temperature, humidity, pressure,
                     vibration, voltage, status_code, anomaly_flag)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()

                write_time = time.time() - write_start
                stats["write_times"].append(write_time)
                stats["writes"] += len(batch)
                stats["batches"] += 1

                batch = []
                last_batch_time = time.time()

                print(json.dumps(stats), flush=True)

            # Control write rate
            time.sleep(1.0 / write_rate)

        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = str(e)
            print(json.dumps(stats), flush=True)

    # Final batch
    if batch:
        cursor.executemany("""
            INSERT INTO sensor_readings
            (timestamp, sensor_id, temperature, humidity, pressure,
             vibration, voltage, status_code, anomaly_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()
        stats["writes"] += len(batch)

    conn.close()

    stats["final"] = True
    if stats["write_times"]:
        stats["avg_write_time"] = sum(stats["write_times"]) / len(stats["write_times"])
    print(json.dumps(stats), flush=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--write-rate", type=int, default=10)
    args = parser.parse_args()

    write_database(args.db_path, args.duration, args.write_rate)
'''

            # Dockerfile
            dockerfile = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*
COPY writer.py /app/writer.py
WORKDIR /app
ENTRYPOINT ["python", "/app/writer.py"]
"""

            dockerfile_path.write_text(dockerfile)
            script_path.write_text(writer_script)

            try:
                subprocess.run(
                    ["docker", "build", "-t", self.writer_image, tmpdir],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                console.print(f"[green]✓ Built writer image: {self.writer_image}[/green]")
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ Failed to build writer: {e.stderr}[/red]")
                return False

    def start_writer(self) -> tuple:
        """Start the writer container."""
        container_name = "sensor-writer"

        # Clean up any existing container
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",
            "-v",
            f"{self.db_path.parent}:/data",  # Mount for read-write
            self.writer_image,
            "--db-path",
            f"/data/{self.db_path.name}",
            "--duration",
            str(self.test_duration),
            "--write-rate",
            str(self.write_rate),
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        return container_name, process

    def start_reader(self, reader_id: int) -> tuple:
        """Start a reader container."""
        container_name = f"sensor-reader-{reader_id}"

        # Clean up any existing container
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",
            "-v",
            f"{self.db_path.parent}:/data:ro",  # Mount read-only
            self.reader_image,
            "--db-path",
            f"/data/{self.db_path.name}",
            "--container-id",
            str(reader_id),
            "--duration",
            str(self.test_duration),
            "--interval",
            str(self.read_interval),
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        return container_name, process

    def collect_stats(self, process, container_type: str, container_id: int | None = None):
        """Collect statistics from container output."""
        for line in process.stdout:
            try:
                stats = json.loads(line.strip())
                if container_type == "writer":
                    self.writer_stats = stats
                else:
                    self.reader_stats[container_id] = stats
            except json.JSONDecodeError:
                pass

    def create_dashboard(self) -> Layout:
        """Create a dashboard layout for monitoring."""
        layout = Layout()

        # Create sections
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4),
        )

        # Header
        header_text = Text("🐳 Container Database Test - Concurrent Read/Write", style="bold blue")
        layout["header"].update(Panel(header_text, box=None))

        # Body - split into writer and readers
        layout["body"].split_row(
            Layout(name="writer", ratio=1),
            Layout(name="readers", ratio=2),
        )

        # Writer stats
        writer_table = Table(show_header=False, box=None)
        writer_table.add_column("Metric", style="cyan")
        writer_table.add_column("Value", style="green")

        if self.writer_stats:
            writer_table.add_row(
                "Status",
                "[green]Writing...[/green]"
                if not self.writer_stats.get("final")
                else "[blue]Complete[/blue]",
            )
            writer_table.add_row("Writes", str(self.writer_stats.get("writes", 0)))
            writer_table.add_row("Batches", str(self.writer_stats.get("batches", 0)))
            writer_table.add_row("Errors", str(self.writer_stats.get("errors", 0)))
            if self.writer_stats.get("avg_write_time"):
                writer_table.add_row(
                    "Avg Write", f"{self.writer_stats['avg_write_time'] * 1000:.1f}ms"
                )
        else:
            writer_table.add_row("Status", "[dim]Starting...[/dim]")

        layout["writer"].update(Panel(writer_table, title="Writer Container", border_style="green"))

        # Reader stats
        reader_table = Table(show_header=True)
        reader_table.add_column("Container", style="cyan", width=12)
        reader_table.add_column("Reads", style="yellow", justify="right")
        reader_table.add_column("Errors", style="red", justify="right")
        reader_table.add_column("Records", style="white", justify="right")
        reader_table.add_column("Avg Read", style="green", justify="right")

        for i in range(self.num_readers):
            if i in self.reader_stats:
                stats = self.reader_stats[i]
                avg_read = "-"
                if stats.get("avg_read_time"):
                    avg_read = f"{stats['avg_read_time'] * 1000:.1f}ms"

                reader_table.add_row(
                    f"reader-{i}",
                    str(stats.get("reads", 0)),
                    str(stats.get("errors", 0)),
                    str(stats.get("total_records", "-")),
                    avg_read,
                )
            else:
                reader_table.add_row(f"reader-{i}", "0", "0", "-", "-")

        layout["readers"].update(
            Panel(reader_table, title="Reader Containers", border_style="blue")
        )

        # Footer - summary
        summary = Text()
        total_reads = sum(s.get("reads", 0) for s in self.reader_stats.values())
        total_writes = self.writer_stats.get("writes", 0)
        summary.append(f"Total Writes: {total_writes} | ", style="green")
        summary.append(f"Total Reads: {total_reads} | ", style="blue")
        summary.append(f"Write Rate: {self.write_rate}/s | ", style="yellow")
        summary.append(f"Readers: {self.num_readers}", style="cyan")

        layout["footer"].update(Panel(summary, title="Summary", border_style="magenta"))

        return layout

    def run_test(self):
        """Run the containerized read/write test."""
        console.print("\n[bold blue]🐳 Container Database Read/Write Test[/bold blue]")
        console.print(f"Testing {self.num_readers} readers with 1 writer across containers\n")

        # Check Docker
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[red]✗ Docker is not available[/red]")
            sys.exit(1)

        # Build images
        if not self.build_images():
            sys.exit(1)

        # Start writer
        console.print("\n[yellow]Starting containers...[/yellow]")
        writer_name, writer_process = self.start_writer()
        self.containers.append(writer_name)
        console.print(f"  [green]✓[/green] Started writer: {writer_name}")

        # Start readers
        processes = []
        for i in range(self.num_readers):
            reader_name, reader_process = self.start_reader(i)
            processes.append((i, reader_name, reader_process))
            self.containers.append(reader_name)
            console.print(f"  [green]✓[/green] Started reader: {reader_name}")

        console.print(
            f"\n[green]All containers started! Monitoring for {self.test_duration}s...[/green]\n"
        )

        # Collect stats in threads
        import threading

        writer_thread = threading.Thread(
            target=self.collect_stats, args=(writer_process, "writer"), daemon=True
        )
        writer_thread.start()

        reader_threads = []
        for reader_id, _, reader_process in processes:
            thread = threading.Thread(
                target=self.collect_stats, args=(reader_process, "reader", reader_id), daemon=True
            )
            thread.start()
            reader_threads.append(thread)

        # Monitor with live dashboard
        start_time = time.time()

        with Live(self.create_dashboard(), refresh_per_second=2, console=console) as live:
            while time.time() - start_time < self.test_duration + 2:
                live.update(self.create_dashboard())
                time.sleep(0.5)

        # Stop containers
        console.print("\n[yellow]Stopping containers...[/yellow]")
        for container in self.containers:
            subprocess.run(
                ["docker", "stop", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            console.print(f"  [green]✓[/green] Stopped: {container}")

        # Final summary
        self.print_final_summary()

    def print_final_summary(self):
        """Print final test summary."""
        console.print("\n[bold green]Final Test Results[/bold green]")

        table = Table(show_header=False)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green")

        # Writer stats
        total_writes = self.writer_stats.get("writes", 0)
        write_errors = self.writer_stats.get("errors", 0)
        avg_write = self.writer_stats.get("avg_write_time", 0) * 1000

        # Reader stats
        total_reads = sum(s.get("reads", 0) for s in self.reader_stats.values())
        read_errors = sum(s.get("errors", 0) for s in self.reader_stats.values())
        avg_reads = [
            s.get("avg_read_time", 0) for s in self.reader_stats.values() if s.get("avg_read_time")
        ]
        avg_read = (sum(avg_reads) / len(avg_reads) * 1000) if avg_reads else 0

        table.add_row("Test Duration", f"{self.test_duration}s")
        table.add_row("Total Writes", str(total_writes))
        table.add_row("Write Errors", str(write_errors))
        table.add_row("Avg Write Time", f"{avg_write:.2f}ms")
        table.add_row("", "")
        table.add_row("Total Reads", str(total_reads))
        table.add_row("Read Errors", str(read_errors))
        table.add_row("Avg Read Time", f"{avg_read:.2f}ms")
        table.add_row("", "")
        table.add_row("Write/Read Ratio", f"{total_writes}/{total_reads}")
        table.add_row(
            "Success Rate",
            f"{100 * (1 - (write_errors + read_errors) / max(1, total_writes + total_reads)):.1f}%",
        )

        console.print(table)


@click.command()
@click.option("--num-readers", "-r", default=3, help="Number of reader containers")
@click.option("--duration", "-d", default=30, help="Test duration in seconds")
@click.option("--write-rate", "-w", default=10, help="Writes per second")
@click.option("--read-interval", "-i", default=0.5, help="Read interval in seconds")
@click.option("--db-path", "-p", default="data/container_test.db", help="Database path")
def main(num_readers: int, duration: int, write_rate: int, read_interval: float, db_path: str):
    """
    Test concurrent database read/write using Docker containers.

    Creates one writer container and multiple reader containers to test
    SQLite WAL mode behavior across container boundaries.

    Examples:

        # Default test with 3 readers
        ./test_containers_rw.py

        # Test with 5 readers and higher write rate
        ./test_containers_rw.py -r 5 -w 20

        # Longer test with faster reads
        ./test_containers_rw.py -d 60 -i 0.2
    """

    orchestrator = ContainerOrchestrator(
        db_path=db_path,
        num_readers=num_readers,
        test_duration=duration,
        write_rate=write_rate,
        read_interval=read_interval,
    )

    try:
        orchestrator.run_test()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted[/yellow]")
        for container in orchestrator.containers:
            subprocess.run(
                ["docker", "stop", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
