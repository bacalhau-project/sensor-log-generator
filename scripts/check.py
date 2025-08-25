#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich>=13.7.0",
#     "click>=8.1.7",
# ]
# ///

"""
Development check script - runs linting, type checking, and tests.
This mimics what pre-commit hooks will do.
"""

import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


def run_command(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    console.print(f"\n[blue]🔍 {description}...[/blue]")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            console.print(f"[green]✅ {description} passed[/green]")
            return True, result.stdout
        else:
            console.print(f"[red]❌ {description} failed[/red]")
            if result.stdout:
                console.print("[dim]Output:[/dim]")
                console.print(result.stdout)
            if result.stderr:
                console.print("[dim]Errors:[/dim]")
                console.print(result.stderr)
            return False, result.stderr or result.stdout
    except Exception as e:
        console.print(f"[red]❌ {description} error: {e}[/red]")
        return False, str(e)


@click.command()
@click.option("--lint/--no-lint", default=True, help="Run linting checks")
@click.option("--typecheck/--no-typecheck", default=True, help="Run type checking")
@click.option("--test/--no-test", default=True, help="Run tests")
@click.option("--fast", is_flag=True, help="Run only fast tests")
@click.option("--fix", is_flag=True, help="Auto-fix linting issues")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(lint: bool, typecheck: bool, test: bool, fast: bool, fix: bool, verbose: bool):
    """
    Run development checks before committing.

    This runs the same checks that pre-commit hooks will run.
    """
    console.print("\n[bold blue]🚀 Running development checks...[/bold blue]\n")

    results = []

    # Python syntax check
    if lint:
        cmd = ["python", "-m", "py_compile", "main.py"]
        success, _ = run_command(cmd, "Python syntax check")
        results.append(("Syntax", success))

    # Ruff linting
    if lint:
        cmd = ["uv", "run", "ruff", "check", "src/", "tests/", "main.py"]
        if fix:
            cmd.append("--fix")
        success, _ = run_command(cmd, "Ruff linting")
        results.append(("Linting", success))

        # Ruff formatting
        cmd = ["uv", "run", "ruff", "format"]
        if not fix:
            cmd.append("--check")
        cmd.extend(["src/", "tests/", "main.py"])
        success, _ = run_command(cmd, "Ruff formatting")
        results.append(("Formatting", success))

    # Type checking
    if typecheck:
        cmd = ["uv", "run", "mypy", "src/", "main.py", "--ignore-missing-imports"]
        success, _ = run_command(cmd, "Type checking")
        results.append(("Type Check", success))

    # Tests
    if test:
        if fast:
            cmd = [
                "uv",
                "run",
                "pytest",
                "tests/",
                "-m",
                "not slow and not integration",
                "--tb=short",
                "-q",
                "--disable-warnings",
                "--maxfail=3",
            ]
            test_desc = "Fast tests"
        else:
            cmd = ["uv", "run", "pytest", "tests/", "-v"]
            if verbose:
                cmd.append("--tb=long")
            else:
                cmd.append("--tb=short")
            test_desc = "All tests"

        success, _ = run_command(cmd, test_desc)
        results.append((test_desc, success))

    # Summary
    console.print("\n[bold]📊 Summary:[/bold]")

    table = Table(show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    all_passed = True
    for check, passed in results:
        status = "✅ Passed" if passed else "❌ Failed"
        style = "green" if passed else "red"
        table.add_row(check, f"[{style}]{status}[/{style}]")
        if not passed:
            all_passed = False

    console.print(table)

    if all_passed:
        console.print("\n[bold green]✨ All checks passed! Ready to commit.[/bold green]")
        sys.exit(0)
    else:
        console.print(
            "\n[bold red]⚠️  Some checks failed. Please fix issues before committing.[/bold red]"
        )
        console.print("[dim]Tip: Use --fix flag to auto-fix linting issues[/dim]")
        console.print(
            "[dim]Tip: Use 'git commit --no-verify' to skip hooks (not recommended)[/dim]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
