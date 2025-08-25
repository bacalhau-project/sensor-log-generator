#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.7.0",
#     "click>=8.1.7",
# ]
# ///

"""
Setup script for development environment.
Sets up pre-commit hooks and installs dependencies.
"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def run_command(cmd: list, description: str, check: bool = True) -> bool:
    """Run a command and return success status."""
    console.print(f"[blue]→ {description}...[/blue]")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        if result.returncode == 0:
            console.print(f"[green]  ✓ {description} complete[/green]")
            return True
        else:
            console.print(f"[red]  ✗ {description} failed[/red]")
            if result.stderr:
                console.print(f"[dim]  Error: {result.stderr}[/dim]")
            return False
    except Exception as e:
        console.print(f"[red]  ✗ {description} error: {e}[/red]")
        return False


@click.command()
@click.option("--skip-hooks", is_flag=True, help="Skip pre-commit hook installation")
@click.option("--dev", is_flag=True, help="Install development dependencies")
def main(skip_hooks: bool, dev: bool):
    """
    Setup development environment for sensor-log-generator.

    This script:
    1. Installs project dependencies
    2. Sets up pre-commit hooks (CRITICAL for code quality)
    3. Runs initial checks to ensure everything works
    """

    console.print(
        Panel.fit(
            "[bold blue]🚀 Sensor Log Generator - Development Setup[/bold blue]\n\n"
            "This will set up your development environment with:\n"
            "• Project dependencies\n"
            "• Pre-commit hooks (prevents broken commits)\n"
            "• Code quality tools",
            border_style="blue",
        )
    )

    console.print("\n[bold]Step 1: Installing dependencies[/bold]")

    # Install dependencies
    if dev:
        success = run_command(
            ["uv", "sync", "--frozen", "--all-extras"],
            "Installing all dependencies (including dev)",
        )
    else:
        success = run_command(["uv", "sync", "--frozen"], "Installing production dependencies")

    if not success:
        console.print("[red]Failed to install dependencies![/red]")
        sys.exit(1)

    if not skip_hooks:
        console.print("\n[bold]Step 2: Setting up pre-commit hooks[/bold]")
        console.print("[dim]This ensures code quality by running checks before each commit[/dim]")

        # Install pre-commit
        run_command(["uv", "pip", "install", "pre-commit"], "Installing pre-commit")

        # Check for existing hooks path that might conflict
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout.strip():
            console.print("[yellow]  ⚠ Removing conflicting hooks path[/yellow]")
            run_command(
                ["git", "config", "--unset-all", "core.hooksPath"],
                "Unsetting hooks path",
                check=False,
            )

        # Install pre-commit hooks
        success = run_command(["uv", "run", "pre-commit", "install"], "Installing pre-commit hooks")

        if success:
            run_command(
                ["uv", "run", "pre-commit", "install", "--hook-type", "pre-push"],
                "Installing pre-push hooks",
            )

        # Install hook environments
        console.print("[blue]→ Setting up hook environments (this may take a minute)...[/blue]")
        result = subprocess.run(
            ["uv", "run", "pre-commit", "install-hooks"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            console.print("[green]  ✓ Hook environments ready[/green]")
        else:
            console.print("[yellow]  ⚠ Some hooks may need to be installed on first run[/yellow]")

    console.print("\n[bold]Step 3: Verifying setup[/bold]")

    # Quick verification
    checks = [
        (["uv", "run", "python", "-c", "import src.simulator"], "Python imports"),
        (["uv", "run", "ruff", "--version"], "Ruff linter"),
        (["uv", "run", "mypy", "--version"], "MyPy type checker"),
        (["uv", "run", "pytest", "--version"], "Pytest"),
    ]

    all_good = True
    for cmd, name in checks:
        result = subprocess.run(cmd, capture_output=True, check=False)
        if result.returncode == 0:
            console.print(f"[green]  ✓ {name} is working[/green]")
        else:
            console.print(f"[red]  ✗ {name} is not working[/red]")
            all_good = False

    # Summary
    console.print("\n" + "=" * 60)

    if all_good:
        console.print(
            Panel.fit(
                "[bold green]✨ Setup complete![/bold green]\n\n"
                "You're ready to start developing! Here are some useful commands:\n\n"
                "[cyan]Before committing:[/cyan]\n"
                "  uv run scripts/check.py     # Run all checks\n"
                "  uv run scripts/check.py --fix  # Auto-fix issues\n\n"
                "[cyan]Testing:[/cyan]\n"
                "  uv run pytest tests/        # Run all tests\n"
                "  uv run pytest tests/ -v     # Verbose test output\n\n"
                "[cyan]Running the simulator:[/cyan]\n"
                "  uv run main.py              # Run with defaults\n"
                "  docker-compose up           # Run in Docker\n\n"
                "[cyan]Building:[/cyan]\n"
                "  uv run build.py --skip-push # Build Docker image locally\n\n"
                "[yellow]⚠️  Important:[/yellow] Pre-commit hooks are now active!\n"
                "Tests and checks will run automatically before each commit.\n"
                "Use 'git commit --no-verify' only in emergencies.",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold yellow]⚠️  Setup completed with warnings[/bold yellow]\n\n"
                "Some tools may not be working correctly.\n"
                "Try running: uv sync --frozen --all-extras",
                border_style="yellow",
            )
        )


if __name__ == "__main__":
    main()
