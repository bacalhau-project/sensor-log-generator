#!/usr/bin/env -S uv run python
"""
Test concurrent database readers using Docker containers.

This script spawns multiple Docker containers that mount and read from
the same SQLite database to test cross-container database access patterns.
"""

import json
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


class ContainerizedReaderTest:
    """Manage containerized database reader tests."""

    def __init__(
        self,
        db_path: str,
        num_containers: int,
        test_duration: int,
        read_interval: float,
        image_name: str = "sensor-reader-test",
    ):
        self.db_path = Path(db_path).resolve()
        self.num_containers = num_containers
        self.test_duration = test_duration
        self.read_interval = read_interval
        self.image_name = image_name
        self.containers: list[str] = []
        self.reader_stats: dict[int, dict] = {}

        # Verify database exists
        if not self.db_path.exists():
            console.print(f"[red]✗ Database not found: {self.db_path}[/red]")
            sys.exit(1)

    def build_reader_image(self):
        """Build a lightweight Docker image for reading the database."""
        console.print("[blue]🔨 Building reader container image...[/blue]")

        # Create a temporary directory for the Docker build
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            reader_script_path = Path(tmpdir) / "reader.py"

            # Create a simple reader script
            reader_script = '''#!/usr/bin/env python3
import sqlite3
import json
import sys
import time
import os
from datetime import datetime

def read_database(db_path, container_id, duration, interval):
    """Read from database and report statistics."""
    start_time = time.time()
    stats = {
        "container_id": container_id,
        "reads": 0,
        "errors": 0,
        "total_records": 0,
        "latest_record": None,
        "read_times": []
    }

    while time.time() - start_time < duration:
        try:
            read_start = time.time()

            # Connect with read-only mode
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA journal_mode = WAL")

            cursor = conn.cursor()

            # Get total count
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
                    "sensor_id": latest[2],
                    "temperature": latest[3]
                }

            conn.close()

            read_time = time.time() - read_start
            stats["read_times"].append(read_time)
            stats["reads"] += 1

            # Output current stats as JSON
            print(json.dumps(stats), flush=True)

        except Exception as e:
            stats["errors"] += 1
            stats["last_error"] = str(e)
            print(json.dumps(stats), flush=True)

        time.sleep(interval)

    # Final stats
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

            # Create Dockerfile
            dockerfile_content = """FROM python:3.11-slim

# Install SQLite3
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

# Copy reader script
COPY reader.py /app/reader.py
RUN chmod +x /app/reader.py

WORKDIR /app

# Default command
ENTRYPOINT ["python", "/app/reader.py"]
"""

            # Write files
            dockerfile_path.write_text(dockerfile_content)
            reader_script_path.write_text(reader_script)

            # Build the image
            try:
                subprocess.run(
                    ["docker", "build", "-t", self.image_name, tmpdir],
                    stdout=subprocess.DEVNULL,
                    text=True,
                    check=True,
                )
                console.print(f"[green]✓ Image built: {self.image_name}[/green]")
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"[red]✗ Failed to build image: {e.stderr}[/red]")
                return False

    def start_container(self, container_id: int) -> str:
        """Start a reader container."""
        container_name = f"reader-{container_id}"

        # Remove any existing container with the same name
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Start the container
        cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",  # Auto-remove when stopped
            "-v",
            f"{self.db_path.parent}:/data:ro",  # Mount database directory as read-only
            self.image_name,
            "--db-path",
            f"/data/{self.db_path.name}",
            "--container-id",
            str(container_id),
            "--duration",
            str(self.test_duration),
            "--interval",
            str(self.read_interval),
        ]

        # Start container in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        return container_name, process

    def collect_stats(self, process, container_id: int):
        """Collect statistics from a container's output."""
        for line in process.stdout:
            try:
                stats = json.loads(line.strip())
                self.reader_stats[container_id] = stats
            except json.JSONDecodeError:
                pass

    def run_test(self):
        """Run the containerized reader test."""
        console.print("\n[bold blue]🐳 Containerized Database Reader Test[/bold blue]")
        console.print(
            f"Testing cross-container read access with {self.num_containers} containers\n"
        )

        # Verify Docker is available
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[red]✗ Docker is not available or not running[/red]")
            sys.exit(1)

        # Build the reader image
        if not self.build_reader_image():
            sys.exit(1)

        # Get initial database stats
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            initial_count = cursor.fetchone()[0]
            conn.close()
            console.print(f"[green]✓ Database accessible:[/green] {self.db_path}")
            console.print(f"[green]✓ Initial record count:[/green] {initial_count}\n")
        except Exception as e:
            console.print(f"[red]✗ Cannot read database: {e}[/red]")
            sys.exit(1)

        # Start containers
        processes = []
        console.print("[yellow]Starting containers...[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Starting containers", total=self.num_containers)

            for i in range(self.num_containers):
                container_name, process = self.start_container(i)
                processes.append((i, container_name, process))
                self.containers.append(container_name)
                progress.advance(task)
                console.print(f"  [green]✓[/green] Started container: {container_name}")

        console.print(f"\n[green]All {self.num_containers} containers started![/green]\n")

        # Monitor containers
        import threading

        # Start threads to collect stats from each container
        threads = []
        for container_id, container_name, process in processes:
            thread = threading.Thread(
                target=self.collect_stats, args=(process, container_id), daemon=True
            )
            thread.start()
            threads.append(thread)

        # Display live stats
        start_time = time.time()

        with Live(console=console, refresh_per_second=2) as live:
            while time.time() - start_time < self.test_duration + 2:
                table = self.create_stats_table()
                panel = Panel(
                    table,
                    title=f"Container Reader Statistics (Elapsed: {int(time.time() - start_time)}s)",
                    border_style="blue",
                )
                live.update(panel)
                time.sleep(0.5)

        # Stop containers
        console.print("\n[yellow]Stopping containers...[/yellow]")
        for container_name in self.containers:
            subprocess.run(
                ["docker", "stop", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            console.print(f"  [green]✓[/green] Stopped: {container_name}")

        # Final summary
        self.print_summary()

    def create_stats_table(self) -> Table:
        """Create a statistics table for display."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Container", style="cyan", width=12)
        table.add_column("Reads", style="yellow", justify="right", width=8)
        table.add_column("Errors", style="red", justify="right", width=8)
        table.add_column("Records", style="white", justify="right", width=10)
        table.add_column("Latest ID", style="blue", justify="right", width=10)
        table.add_column("Avg Read (ms)", style="green", justify="right", width=12)
        table.add_column("Status", style="white", width=15)

        for i in range(self.num_containers):
            if i in self.reader_stats:
                stats = self.reader_stats[i]

                if stats.get("final"):
                    status = "[green]Complete[/green]"
                elif stats.get("errors", 0) > 0:
                    status = "[yellow]Reading (errors)[/yellow]"
                else:
                    status = "[green]Reading...[/green]"

                avg_read = "-"
                if "avg_read_time" in stats:
                    avg_read = f"{stats['avg_read_time'] * 1000:.1f}"
                elif stats.get("read_times"):
                    avg_time = sum(stats["read_times"]) / len(stats["read_times"])
                    avg_read = f"{avg_time * 1000:.1f}"

                latest_id = "-"
                if stats.get("latest_record"):
                    latest_id = str(stats["latest_record"]["id"])

                table.add_row(
                    f"reader-{i}",
                    str(stats.get("reads", 0)),
                    str(stats.get("errors", 0)),
                    str(stats.get("total_records", "-")),
                    latest_id,
                    avg_read,
                    status,
                )
            else:
                table.add_row(f"reader-{i}", "0", "0", "-", "-", "-", "[dim]Starting...[/dim]")

        return table

    def print_summary(self):
        """Print test summary."""
        console.print("\n[bold green]Test Summary[/bold green]")

        total_reads = sum(s.get("reads", 0) for s in self.reader_stats.values())
        total_errors = sum(s.get("errors", 0) for s in self.reader_stats.values())

        summary = Table(show_header=False)
        summary.add_column("Metric", style="cyan")
        summary.add_column("Value", style="green")

        summary.add_row("Total Containers", str(self.num_containers))
        summary.add_row("Test Duration", f"{self.test_duration}s")
        summary.add_row("Total Reads", str(total_reads))
        summary.add_row("Total Errors", str(total_errors))
        summary.add_row("Success Rate", f"{(1 - total_errors / max(1, total_reads)) * 100:.1f}%")

        console.print(summary)


@click.command()
@click.option(
    "--num-containers",
    "-c",
    default=3,
    help="Number of reader containers to spawn",
)
@click.option(
    "--duration",
    "-d",
    default=30,
    help="Test duration in seconds",
)
@click.option(
    "--interval",
    "-i",
    default=0.5,
    help="Read interval in seconds",
)
@click.option(
    "--db-path",
    "-p",
    default="data/sensor_data.db",
    help="Path to the SQLite database",
)
def main(num_containers: int, duration: int, interval: float, db_path: str):
    """
    Test concurrent database readers using Docker containers.

    This creates lightweight Docker containers that mount and read from
    the same SQLite database to test cross-container access patterns.

    Examples:

        # Test with 3 containers for 30 seconds
        ./test_readers_containerized.py

        # Test with 5 containers for 60 seconds
        ./test_readers_containerized.py -c 5 -d 60

        # Test with faster read interval
        ./test_readers_containerized.py -i 0.1
    """

    tester = ContainerizedReaderTest(
        db_path=db_path,
        num_containers=num_containers,
        test_duration=duration,
        read_interval=interval,
    )

    try:
        tester.run_test()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        # Clean up containers
        for container in tester.containers:
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
