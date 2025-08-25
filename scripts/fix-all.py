#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.7.0",
#     "click>=8.1.7",
# ]
# ///

"""
Fix all linting and formatting issues automatically.
This script aggressively fixes all auto-fixable issues.
"""

import subprocess

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def run_command(cmd: list, description: str, check: bool = False) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        if result.returncode == 0:
            return True
        else:
            if result.stderr and "error" in result.stderr.lower():
                console.print(f"[yellow]⚠ {description}: Some issues remain[/yellow]")
            return False
    except Exception as e:
        console.print(f"[red]✗ {description}: {e}[/red]")
        return False


@click.command()
@click.option("--aggressive", is_flag=True, help="Apply more aggressive fixes")
@click.option("--test", is_flag=True, help="Run fast tests after fixing")
def main(aggressive: bool, test: bool):
    """
    Automatically fix all linting and formatting issues.

    This will:
    1. Format all Python files with Ruff
    2. Fix all auto-fixable linting issues
    3. Sort imports
    4. Remove trailing whitespace
    5. Optionally run tests to verify nothing broke
    """

    console.print("\n[bold blue]🔧 Auto-fixing all issues...[/bold blue]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Format with Ruff
        task = progress.add_task("[cyan]Formatting code with Ruff...", total=None)
        run_command(["uv", "run", "ruff", "format", "src/", "tests/", "main.py"], "Ruff format")
        progress.update(task, completed=True)

        # Step 2: Fix imports
        task = progress.add_task("[cyan]Fixing imports...", total=None)
        run_command(
            ["uv", "run", "ruff", "check", "--select", "I", "--fix", "src/", "tests/", "main.py"],
            "Import sorting",
        )
        progress.update(task, completed=True)

        # Step 3: Fix basic issues
        task = progress.add_task("[cyan]Fixing basic linting issues...", total=None)
        run_command(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "--fix",
                "--select",
                "F,E,W",
                "src/",
                "tests/",
                "main.py",
            ],
            "Basic fixes",
        )
        progress.update(task, completed=True)

        if aggressive:
            # Step 4: Fix more issues (including removing commented code)
            task = progress.add_task("[cyan]Applying aggressive fixes...", total=None)

            # Fix redundant exception messages
            run_command(
                [
                    "uv",
                    "run",
                    "ruff",
                    "check",
                    "--fix",
                    "--select",
                    "TRY",
                    "src/",
                    "tests/",
                    "main.py",
                ],
                "Exception fixes",
            )

            # Fix simplifications
            run_command(
                [
                    "uv",
                    "run",
                    "ruff",
                    "check",
                    "--fix",
                    "--select",
                    "SIM",
                    "src/",
                    "tests/",
                    "main.py",
                ],
                "Simplifications",
            )

            # Fix comprehensions and modern syntax
            run_command(
                [
                    "uv",
                    "run",
                    "ruff",
                    "check",
                    "--fix",
                    "--select",
                    "UP,C4",
                    "src/",
                    "tests/",
                    "main.py",
                ],
                "Modernization",
            )

            # Apply unsafe fixes for commented code removal
            run_command(
                [
                    "uv",
                    "run",
                    "ruff",
                    "check",
                    "--fix",
                    "--unsafe-fixes",
                    "--select",
                    "ERA",
                    "src/",
                    "tests/",
                    "main.py",
                ],
                "Remove commented code",
            )

            progress.update(task, completed=True)

        # Step 5: Final format pass
        task = progress.add_task("[cyan]Final formatting pass...", total=None)
        run_command(["uv", "run", "ruff", "format", "src/", "tests/", "main.py"], "Final format")
        progress.update(task, completed=True)

    # Show remaining issues
    console.print("\n[bold]📊 Checking remaining issues...[/bold]\n")

    result = subprocess.run(
        ["uv", "run", "ruff", "check", "src/", "tests/", "main.py"], capture_output=True, text=True
    )

    if result.returncode == 0:
        console.print("[bold green]✨ All auto-fixable issues resolved![/bold green]")
    else:
        # Count remaining issues
        lines = result.stdout.strip().split("\n")
        error_count = 0
        for line in lines:
            if "Found" in line and "error" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "Found":
                        try:
                            error_count = int(parts[i + 1])
                        except (ValueError, IndexError):
                            pass

        if error_count > 0:
            console.print(
                f"[yellow]⚠ {error_count} issues remain that need manual fixing:[/yellow]\n"
            )

            # Show first few remaining issues
            shown = 0
            for line in lines[:20]:
                if line.strip() and not line.startswith("warning:"):
                    console.print(f"  {line}")
                    shown += 1

            if error_count > shown:
                console.print(f"\n  ... and {error_count - shown} more issues")

            console.print("\n[dim]These issues may require manual intervention.[/dim]")

    # Run tests if requested
    if test:
        console.print("\n[bold]🧪 Running fast tests...[/bold]\n")

        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "tests/",
                "-m",
                "not slow and not integration",
                "-q",
                "--tb=no",
                "--no-header",
                "--disable-warnings",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Extract test count from output
            output_lines = result.stdout.strip().split("\n")
            for line in output_lines:
                if "passed" in line:
                    console.print(f"[green]✅ Tests: {line}[/green]")
                    break
        else:
            console.print("[red]❌ Some tests failed[/red]")
            console.print("[dim]Run 'uv run pytest tests/ -v' for details[/dim]")

    console.print("\n[bold]💡 Tips:[/bold]")
    console.print("  • Use --aggressive to remove commented code and apply more fixes")
    console.print("  • Use --test to run fast tests after fixing")
    console.print("  • Run 'uv run scripts/check.py' for a full check")
    console.print("  • Some issues may need manual fixing (check type annotations)")


if __name__ == "__main__":
    main()
