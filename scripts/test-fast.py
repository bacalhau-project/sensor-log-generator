#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.7.0",
#     "click>=8.1.7",
# ]
# ///

"""
Run tests efficiently with different speed profiles.
"""

import subprocess
import sys
import time

import click
from rich.console import Console
from rich.table import Table

console = Console()


def run_tests(cmd: list, description: str) -> tuple[bool, float, str]:
    """Run tests and return (success, duration, summary)."""
    start = time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        duration = time.time() - start

        # Parse output for summary
        summary = "No tests run"
        for line in result.stdout.split("\n"):
            if "passed" in line or "failed" in line:
                summary = line.strip()
                break

        return result.returncode == 0, duration, summary
    except Exception as e:
        return False, time.time() - start, str(e)


@click.command()
@click.option(
    "--level",
    type=click.Choice(["critical", "fast", "normal", "full", "integration"]),
    default="fast",
    help="Test level to run",
)
@click.option("--parallel", "-p", is_flag=True, help="Run tests in parallel")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--coverage", is_flag=True, help="Include coverage report")
@click.option("--failed-first", is_flag=True, help="Run failed tests first")
def main(level: str, parallel: bool, verbose: bool, coverage: bool, failed_first: bool):
    """
    Run tests at different speed levels.

    Levels:
    - critical: Only the most critical tests (~5 seconds)
    - fast: Quick unit tests (~30 seconds)
    - normal: Standard test suite (~1 minute)
    - full: All tests with coverage (~2 minutes)
    - integration: Only integration tests
    """

    console.print(f"\n[bold blue]🧪 Running {level} tests...[/bold blue]\n")

    # Base command
    cmd = ["uv", "run", "pytest"]

    # Configure based on level
    if level == "critical":
        # Only run most critical tests
        cmd.extend(
            [
                "tests/test_config.py",
                "tests/test_enums.py",
                "tests/test_database.py::TestDatabaseConnectionManager",
                "-q",
                "--tb=no",
                "--disable-warnings",
            ]
        )
        expected_time = "~5 seconds"

    elif level == "fast":
        # Fast unit tests only
        cmd.extend(
            [
                "tests/",
                "-m",
                "not slow and not integration",
                "-q",
                "--tb=short",
                "--disable-warnings",
            ]
        )
        expected_time = "~30 seconds"

    elif level == "normal":
        # Standard test suite
        cmd.extend(["tests/", "-m", "not integration", "--tb=short"])
        expected_time = "~1 minute"

    elif level == "full":
        # Everything
        cmd.extend(["tests/", "--tb=short"])
        expected_time = "~2 minutes"

    elif level == "integration":
        # Integration tests only
        cmd.extend(["tests/", "-m", "integration", "--tb=short"])
        expected_time = "~1 minute"

    # Add options
    if parallel:
        cmd.extend(["-n", "auto"])  # Requires pytest-xdist
        console.print("[dim]Running tests in parallel...[/dim]")

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("--quiet")

    if coverage and level != "critical":
        cmd.extend(["--cov=src", "--cov-report=term-missing:skip-covered"])

    if failed_first:
        cmd.append("--failed-first")

    # Show what we're running
    console.print(f"[dim]Expected time: {expected_time}[/dim]")
    if verbose:
        console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")
    console.print()

    # Run tests
    success, duration, summary = run_tests(cmd, level)

    # Display results
    console.print()
    if success:
        console.print(f"[bold green]✅ {level.capitalize()} tests passed![/bold green]")
    else:
        console.print(f"[bold red]❌ {level.capitalize()} tests failed![/bold red]")

    console.print(f"[dim]Duration: {duration:.1f} seconds[/dim]")
    console.print(f"[dim]Summary: {summary}[/dim]")

    # Suggestions for speed
    if duration > 60 and level != "full":
        console.print("\n[yellow]💡 Tests are running slow. Try:[/yellow]")
        console.print("  • Use --parallel to run in parallel (install pytest-xdist)")
        console.print("  • Use --level=fast for quicker feedback")
        console.print("  • Use --failed-first to run previously failed tests first")

    # Test level recommendations
    console.print("\n[bold]📊 Test Levels:[/bold]")

    table = Table(show_header=True)
    table.add_column("Level", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Use Case", style="white")

    table.add_row("critical", "~5s", "Pre-commit, quick validation")
    table.add_row("fast", "~30s", "Regular development [default]")
    table.add_row("normal", "~1m", "Before pushing changes")
    table.add_row("full", "~2m", "Complete validation")
    table.add_row("integration", "~1m", "Test system integration")

    console.print(table)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
