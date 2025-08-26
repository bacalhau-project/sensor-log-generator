#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1.7",
#     "rich>=13.7.0",
# ]
# ///

"""
Test concurrent readers against an existing sensor database.
This script only reads from the database - it doesn't start the sensor simulator.
"""

import multiprocessing
import signal
import sqlite3
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.table import Table

console = Console()


def reader_process(
    db_path: str,
    reader_id: int,
    duration: int,
    interval: float,
    results_queue: multiprocessing.Queue,
):
    """
    Individual reader process that queries the database.

    Args:
        db_path: Path to the SQLite database
        reader_id: Unique identifier for this reader
        duration: How long to run (seconds)
        interval: Time between reads (seconds)
        results_queue: Queue to report results
    """
    # Ignore keyboard interrupts in child processes
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    start_time = time.time()
    read_count = 0
    error_count = 0
    last_count = 0
    last_id = None

    while time.time() - start_time < duration:
        try:
            # Use read-only connection
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            cursor = conn.cursor()

            # Get current count
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            count = cursor.fetchone()[0]

            # Get latest reading
            cursor.execute("""
                SELECT id, timestamp, sensor_id, temperature, humidity
                FROM sensor_readings
                ORDER BY id DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()

            conn.close()

            read_count += 1
            latest_id = latest[0] if latest else None

            # Report progress
            results_queue.put(
                {
                    "reader_id": reader_id,
                    "count": count,
                    "latest_id": latest_id,
                    "latest_temp": latest[3] if latest else None,
                    "reads": read_count,
                    "errors": error_count,
                    "new_records": count - last_count if last_count > 0 else 0,
                }
            )

            last_count = count
            last_id = latest_id

        except sqlite3.OperationalError as e:
            error_count += 1
            results_queue.put(
                {
                    "reader_id": reader_id,
                    "error": str(e),
                    "reads": read_count,
                    "errors": error_count,
                }
            )

        except Exception:
            error_count += 1
            # Don't print in child processes to avoid output mess
            pass

        try:
            time.sleep(interval)
        except (KeyboardInterrupt, SystemExit):
            # Gracefully handle interrupts during sleep
            break

    # Final report
    results_queue.put(
        {
            "reader_id": reader_id,
            "final": True,
            "reads": read_count,
            "errors": error_count,
            "total_reads": read_count,
            "total_errors": error_count,
            "count": last_count,
            "latest_id": last_id,
            "duration": time.time() - start_time,
        }
    )


def monitor_readers(
    results_queue: multiprocessing.Queue,
    num_readers: int,
    duration: int,
):
    """
    Monitor and display results from all reader processes.

    Args:
        results_queue: Queue receiving results from readers
        num_readers: Number of reader processes
        duration: Expected duration (for progress display)
    """
    reader_stats = {}
    start_time = time.time()
    completed_readers = 0

    def create_table():
        """Create a status table for display"""
        table = Table(title="Concurrent Database Readers", show_header=True)
        table.add_column("Reader", style="cyan", width=8)
        table.add_column("Reads", style="yellow", justify="right", width=8)
        table.add_column("Errors", style="red", justify="right", width=8)
        table.add_column("Records", style="white", justify="right", width=10)
        table.add_column("Latest ID", style="blue", justify="right", width=10)
        table.add_column("New/sec", style="green", justify="right", width=8)
        table.add_column("Status", style="white", width=15)

        # Add rows for each reader
        for reader_id in range(num_readers):
            if reader_id in reader_stats:
                stats = reader_stats[reader_id]
                if stats.get("final"):
                    status = "[green]Complete[/green]"
                elif stats.get("error"):
                    status = "[red]Error[/red]"
                else:
                    status = "[yellow]Reading...[/yellow]"

                table.add_row(
                    f"#{reader_id}",
                    str(stats.get("reads", 0)),
                    str(stats.get("errors", 0)),
                    str(stats.get("count", "-")),
                    str(stats.get("latest_id", "-")),
                    f"{stats.get('new_records', 0):.1f}",
                    status,
                )
            else:
                table.add_row(f"#{reader_id}", "0", "0", "-", "-", "0.0", "[dim]Starting...[/dim]")

        # Add summary row
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{sum(s.get('reads', 0) for s in reader_stats.values())}[/bold]",
            f"[bold]{sum(s.get('errors', 0) for s in reader_stats.values())}[/bold]",
            "-",
            "-",
            "-",
            "-",
            f"[bold]{completed_readers}/{num_readers}[/bold]",
        )

        # Add timing info
        elapsed = time.time() - start_time
        remaining = max(0, duration - elapsed)
        table.caption = f"Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s"

        return table

    with Live(create_table(), refresh_per_second=2, console=console) as live:
        while completed_readers < num_readers and time.time() - start_time < duration + 5:
            try:
                # Get result with timeout
                result = results_queue.get(timeout=0.5)

                reader_id = result.get("reader_id")
                if result.get("final"):
                    completed_readers += 1

                reader_stats[reader_id] = result
                live.update(create_table())

            except Exception:
                # Timeout - just update display
                live.update(create_table())

    # Print final summary
    console.print("\n[bold]Test Complete![/bold]")

    total_reads = sum(s.get("total_reads", s.get("reads", 0)) for s in reader_stats.values())
    total_errors = sum(s.get("total_errors", s.get("errors", 0)) for s in reader_stats.values())

    summary = Table(title="Summary", show_header=True)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green", justify="right")

    summary.add_row("Total Readers", str(num_readers))
    summary.add_row("Total Reads", str(total_reads))
    summary.add_row("Total Errors", str(total_errors))
    summary.add_row("Success Rate", f"{(1 - total_errors / max(1, total_reads)) * 100:.1f}%")
    summary.add_row("Reads/Second", f"{total_reads / duration:.1f}")
    summary.add_row("Test Duration", f"{duration} seconds")

    console.print(summary)


@click.command()
@click.option(
    "--database",
    "-d",
    default="data/sensor_data.db",
    help="Path to the sensor database",
    type=click.Path(exists=True),
)
@click.option(
    "--readers",
    "-r",
    default=10,
    help="Number of concurrent readers",
    type=click.IntRange(1, 100),
)
@click.option(
    "--duration",
    "-t",
    default=30,
    help="Test duration in seconds",
    type=click.IntRange(1, 600),
)
@click.option(
    "--interval",
    "-i",
    default=0.5,
    help="Read interval in seconds",
    type=click.FloatRange(0.1, 10.0),
)
@click.option(
    "--check-writes",
    is_flag=True,
    help="Check if database is being written to",
)
def main(
    database: str,
    readers: int,
    duration: int,
    interval: float,
    check_writes: bool,
):
    """
    Test concurrent readers against an existing sensor database.

    This script spawns multiple reader processes that continuously query
    the database to test read performance and concurrency handling.
    It does NOT start the sensor simulator - it expects the database
    to already exist and optionally be actively written to by another process.

    Examples:

        # Test with 10 readers for 30 seconds
        ./test_readers.py

        # Test with 50 readers for 60 seconds
        ./test_readers.py -r 50 -t 60

        # Test with faster read interval
        ./test_readers.py -i 0.1

        # Check if database is being actively written to
        ./test_readers.py --check-writes
    """

    console.print("\n[bold blue]🔍 Concurrent Database Reader Test[/bold blue]")
    console.print(f"[dim]Testing read performance with {readers} concurrent readers[/dim]\n")

    # Verify database exists and is accessible
    db_path = Path(database)
    if not db_path.exists():
        console.print(f"[red]✗ Database not found: {database}[/red]")
        console.print(
            "[yellow]Make sure the sensor simulator has run at least once to create the database[/yellow]"
        )
        return 1

    # Check database accessibility
    try:
        conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=1.0)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        initial_count = cursor.fetchone()[0]
        conn.close()

        console.print(f"[green]✓[/green] Database accessible: {database}")
        console.print(f"[green]✓[/green] Initial record count: {initial_count:,}")

        # Check if database is being written to
        if check_writes:
            console.print("[yellow]Checking for active writes...[/yellow]")
            time.sleep(2)
            conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=1.0)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            new_count = cursor.fetchone()[0]
            conn.close()

            if new_count > initial_count:
                rate = (new_count - initial_count) / 2.0
                console.print(
                    f"[green]✓[/green] Database is being written to ({rate:.1f} records/sec)"
                )
            else:
                console.print("[yellow]![/yellow] No new writes detected - database may be idle")

    except sqlite3.Error as e:
        console.print(f"[red]✗ Database error: {e}[/red]")
        return 1

    console.print("\n[blue]Starting test:[/blue]")
    console.print(f"  • Readers: {readers}")
    console.print(f"  • Duration: {duration} seconds")
    console.print(f"  • Read interval: {interval} seconds")
    console.print("")

    # Create results queue
    results_queue = multiprocessing.Queue()

    # Start reader processes
    processes = []
    for i in range(readers):
        p = multiprocessing.Process(
            target=reader_process, args=(database, i, duration, interval, results_queue)
        )
        p.start()
        processes.append(p)

    # Monitor results
    try:
        monitor_readers(results_queue, readers, duration)
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    finally:
        # Terminate all processes gracefully
        for p in processes:
            if p.is_alive():
                p.terminate()

        # Give them a moment to terminate
        time.sleep(0.5)

        # Force kill any remaining
        for p in processes:
            if p.is_alive():
                p.kill()
                p.join(timeout=0.5)

    # Clean up the queue
    try:
        while not results_queue.empty():
            results_queue.get_nowait()
    except Exception:
        pass

    console.print("\n[bold green]✓ Test complete![/bold green]")
    return 0


if __name__ == "__main__":
    exit(main())
