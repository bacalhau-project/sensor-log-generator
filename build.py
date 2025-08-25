#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click>=8.1.7",
#     "semver>=3.0.2",
#     "pyyaml>=6.0.2",
#     "rich>=13.7.0",
# ]
# ///

"""
Docker Compose-based multi-platform build and push script with semantic versioning.
Now uses Docker Compose for all build operations instead of direct Docker commands.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import semver
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


class BuildError(Exception):
    """Custom exception for build errors"""

    pass


class DockerComposeBuilder:
    def __init__(
        self,
        image_name: Optional[str] = None,
        platforms: str = "linux/amd64,linux/arm64",
        dockerfile: str = "Dockerfile",
        registry: str = "ghcr.io",
        builder_name: str = "multiarch-builder",
        skip_push: bool = False,
        build_cache: bool = True,
        require_login: bool = True,
        compose_file: str = "docker-compose.build.yml",
        dev_mode: bool = False,
    ):
        self.image_name = image_name or self._get_default_image_name()
        self.platforms = platforms
        self.dockerfile = dockerfile
        self.registry = registry
        self.builder_name = builder_name
        self.skip_push = skip_push
        self.build_cache = build_cache
        self.require_login = require_login
        self.compose_file = compose_file
        self.dev_mode = dev_mode
        self.github_user = os.environ.get("GITHUB_USER") or self._get_git_user()
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.env_vars = {}

    def _get_default_image_name(self) -> str:
        """Get image name from git repository or current directory"""
        try:
            # Get git remote URL
            result = self._run_command(
                ["git", "remote", "get-url", "origin"], check=False, verbose=False
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # Parse GitHub URL
                if "github.com" in remote_url:
                    # Handle both HTTPS and SSH URLs
                    if remote_url.startswith("https://"):
                        parts = (
                            remote_url.replace("https://github.com/", "")
                            .replace(".git", "")
                            .split("/")
                        )
                    elif remote_url.startswith("git@"):
                        parts = (
                            remote_url.replace("git@github.com:", "").replace(".git", "").split("/")
                        )
                    else:
                        parts = []

                    if len(parts) >= 2:
                        return f"{parts[0]}/{parts[1]}"
        except Exception:
            pass

        # Fall back to current directory
        current_dir = Path.cwd().name
        return f"sensor/{current_dir}"

    def _get_git_user(self) -> str:
        """Get git username"""
        try:
            result = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "GITHUB_USER_NOT_SET"

    def _run_command(
        self, cmd: list[str], check: bool = True, verbose: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a command and return the result"""
        if verbose:
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def _run_compose_command(
        self,
        args: list[str],
        check: bool = True,
        verbose: bool = True,
        capture_output: bool = True,
        env: dict = None,
    ) -> subprocess.CompletedProcess:
        """Run a docker compose command with proper environment"""
        # Build the compose command
        cmd = ["docker", "compose"]
        if self.compose_file:
            cmd.extend(["-f", self.compose_file])
        cmd.extend(args)

        if verbose:
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

        # Merge environment variables
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        run_env.update(self.env_vars)

        return subprocess.run(
            cmd, capture_output=capture_output, text=True, check=check, env=run_env
        )

    def validate_requirements(self):
        """Validate all requirements are met"""
        console.print("[blue]Validating requirements...[/blue]")

        # Check for required commands
        for cmd, msg in [
            ("docker", "Docker is required but not installed"),
            ("git", "Git is required but not installed"),
        ]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                raise BuildError(msg)

        # Check Docker Compose support
        result = self._run_command(["docker", "compose", "version"], check=False, verbose=False)
        if result.returncode != 0:
            # Try docker-compose (hyphenated)
            result = self._run_command(["docker-compose", "version"], check=False, verbose=False)
            if result.returncode != 0:
                raise BuildError(
                    "Docker Compose is required but not installed.\n"
                    "Please install Docker Desktop or Docker Compose plugin."
                )

        # Check compose file exists (create if it doesn't)
        if not Path(self.compose_file).exists():
            console.print(f"[yellow]Creating {self.compose_file}...[/yellow]")
            self._create_compose_build_file()

        # Check dockerfile exists
        if not Path(self.dockerfile).exists():
            raise BuildError(f"Dockerfile not found at {self.dockerfile}")

        # Check docker daemon is running
        result = self._run_command(["docker", "info"], check=False, verbose=False)
        if result.returncode != 0:
            raise BuildError("Docker daemon is not running")

        # Check buildx support
        result = self._run_command(["docker", "buildx", "version"], check=False, verbose=False)
        if result.returncode != 0:
            console.print(
                "[yellow]![/yellow] Docker buildx support not available, "
                "multi-platform builds may be limited"
            )

        console.print("[green]✓[/green] All requirements validated")

    def _create_compose_build_file(self):
        """Create a docker-compose.build.yml file if it doesn't exist"""
        # For Docker Compose, platforms should be specified as separate items
        # We'll handle this dynamically based on the platforms string
        platform_list = self.platforms.split(",")

        compose_content = {
            "services": {
                "sensor-simulator": {
                    "image": "${IMAGE_TAG:-ghcr.io/bacalhau-project/sensor-log-generator:latest}",
                    "build": {
                        "context": ".",
                        "dockerfile": "${DOCKERFILE:-Dockerfile}",
                        "platforms": platform_list,
                        "cache_from": [
                            "type=registry,ref=${CACHE_FROM:-ghcr.io/bacalhau-project/sensor-log-generator:buildcache}"
                        ],
                        "cache_to": [
                            "type=registry,ref=${CACHE_TO:-ghcr.io/bacalhau-project/sensor-log-generator:buildcache},mode=max"
                        ],
                        "labels": {
                            "org.opencontainers.image.title": "Sensor Log Generator",
                            "org.opencontainers.image.description": "High-performance sensor data simulator",
                            "org.opencontainers.image.version": "${VERSION:-dev}",
                            "org.opencontainers.image.created": "${BUILD_DATE}",
                            "org.opencontainers.image.revision": "${GIT_COMMIT}",
                        },
                        "args": {
                            "BUILD_DATE": "${BUILD_DATE}",
                            "VERSION": "${VERSION:-dev}",
                            "GIT_COMMIT": "${GIT_COMMIT}",
                        },
                    },
                }
            }
        }

        with open(self.compose_file, "w") as f:
            yaml.dump(compose_content, f, default_flow_style=False, sort_keys=False)

        console.print(f"[green]✓[/green] Created {self.compose_file}")

    def check_docker_login(self):
        """Check and perform Docker registry login"""
        if not self.require_login or self.skip_push:
            return

        console.print("[blue]Checking Docker registry login...[/blue]")

        # Check if we're in CI environment
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            console.print(
                "[dim]Running in CI environment, assuming authentication is handled[/dim]"
            )
            return

        if not self.github_token:
            console.print(
                "[yellow]![/yellow] GITHUB_TOKEN not set, attempting to use existing Docker credentials"
            )
            # Check if already logged in
            result = subprocess.run(
                ["docker", "pull", f"{self.registry}/hello-world"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "pull access denied" in result.stderr or "unauthorized" in result.stderr.lower():
                raise BuildError(
                    "Not logged in to GitHub Container Registry.\n"
                    "Please set GITHUB_TOKEN environment variable or run:\n"
                    f"  echo $GITHUB_TOKEN | docker login {self.registry} -u USERNAME --password-stdin"
                )
            return

        if not self.github_user:
            raise BuildError("GITHUB_USER is not set")

        # Login to registry
        result = subprocess.run(
            ["docker", "login", self.registry, "--username", self.github_user, "--password-stdin"],
            input=self.github_token,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise BuildError(f"Failed to log in to Docker registry: {result.stderr}")

        console.print("[green]✓[/green] Successfully logged in to Docker registry")

    def setup_buildx_builder(self):
        """Setup buildx builder for multi-platform builds"""
        console.print("[blue]Setting up Docker Buildx for multi-platform builds...[/blue]")

        # Check if buildx is available
        result = self._run_command(["docker", "buildx", "version"], check=False, verbose=False)
        if result.returncode != 0:
            console.print(
                "[yellow]![/yellow] Docker Buildx not available, "
                "using standard Docker Compose build"
            )
            return False

        # Check if builder exists
        result = self._run_command(
            ["docker", "buildx", "inspect", self.builder_name], check=False, verbose=False
        )

        if result.returncode == 0:
            # Check if builder is running
            result = self._run_command(
                ["docker", "buildx", "inspect", "--bootstrap", self.builder_name],
                check=False,
                verbose=False,
            )
            if "Status: running" in result.stdout:
                console.print(f"[green]✓[/green] Using existing builder '{self.builder_name}'")
                self._run_command(["docker", "buildx", "use", self.builder_name], verbose=False)
                return True
            else:
                console.print("[yellow]![/yellow] Removing non-functional builder")
                self._run_command(
                    ["docker", "buildx", "rm", self.builder_name], check=False, verbose=False
                )

        # Create new builder
        console.print(f"Creating new builder '{self.builder_name}'...")
        self._run_command(
            [
                "docker",
                "buildx",
                "create",
                "--name",
                self.builder_name,
                "--driver",
                "docker-container",
                "--bootstrap",
            ],
            verbose=False,
        )
        self._run_command(["docker", "buildx", "use", self.builder_name], verbose=False)
        console.print("[green]✓[/green] Builder created and ready")
        return True

    def get_current_version(self) -> Optional[semver.Version]:
        """Get the current version from git tags"""
        try:
            result = self._run_command(["git", "tag", "--list", "v*"], check=False)
            if result.returncode == 0 and result.stdout:
                tags = result.stdout.strip().split("\n")
                # Filter valid semver tags
                versions = []
                for tag in tags:
                    tag = tag.strip()
                    if tag.startswith("v"):
                        tag = tag[1:]
                    try:
                        versions.append(semver.Version.parse(tag))
                    except Exception:
                        continue

                if versions:
                    return max(versions)
        except Exception:
            pass
        return None

    def bump_version(self, current: Optional[semver.Version], bump_type: str) -> semver.Version:
        """Bump the version based on type"""
        if current is None:
            # Start with 1.0.0 if no version exists
            return semver.Version(1, 0, 0)

        if bump_type == "major":
            return current.bump_major()
        elif bump_type == "minor":
            return current.bump_minor()
        elif bump_type == "patch":
            return current.bump_patch()
        else:
            raise BuildError(f"Invalid bump type: {bump_type}")

    def parse_version(self, version_str: str) -> semver.Version:
        """Parse and validate a version string"""
        try:
            # Remove 'v' prefix if present
            if version_str.startswith("v"):
                version_str = version_str[1:]
            return semver.Version.parse(version_str)
        except ValueError as e:
            raise BuildError(f"Invalid semver format '{version_str}': {e}")

    def get_git_info(self) -> tuple[str, str]:
        """Get git commit hash and branch"""
        commit = "unknown"
        branch = "unknown"

        try:
            result = self._run_command(
                ["git", "rev-parse", "--short", "HEAD"], check=False, verbose=False
            )
            if result.returncode == 0:
                commit = result.stdout.strip()

            result = self._run_command(
                ["git", "branch", "--show-current"], check=False, verbose=False
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        return commit, branch

    def prepare_build_env(self, version: semver.Version, datetime_tag: str) -> list[str]:
        """Prepare environment variables for the build"""
        commit, branch = self.get_git_info()
        is_ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")

        base_image = f"{self.registry}/{self.image_name}"

        # Prepare tags based on environment
        tags = []
        if self.dev_mode or not is_ci:
            # Development build
            dev_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            tags = [
                f"{base_image}:dev",
                f"{base_image}:dev-{dev_timestamp}",
                f"{base_image}:{version}-dev",
            ]
            console.print("[yellow]📦 Development mode - building for local testing[/yellow]")
        else:
            # Production build
            tags = [
                f"{base_image}:latest",
                f"{base_image}:{datetime_tag}",
                f"{base_image}:{version}",
                f"{base_image}:v{version}",
            ]

        # Add git commit tag
        if commit != "unknown":
            tags.append(f"{base_image}:{commit}")

        # Build environment variables
        self.env_vars = {
            "IMAGE_TAG": tags[0],
            "PLATFORMS": self.platforms,
            "DOCKERFILE": self.dockerfile,
            "VERSION": str(version),
            "BUILD_DATE": datetime.now().isoformat(),
            "GIT_COMMIT": commit,
            "GIT_BRANCH": branch,
            "REGISTRY": self.registry,
            "IMAGE_NAME": self.image_name,
            "CACHE_FROM": f"{base_image}:buildcache",
            "CACHE_TO": f"{base_image}:buildcache",
        }

        return tags

    def build_and_push_with_compose(
        self, version: semver.Version, datetime_tag: str, tags: list[str]
    ):
        """Build and push images using Docker Compose"""
        console.print(f"[blue]Building with Docker Compose for platforms: {self.platforms}[/blue]")
        console.print("[blue]Tags:[/blue]")
        for tag in tags:
            console.print(f"  • {tag}")

        console.print("\n[yellow]Building images... (this may take a few minutes)[/yellow]")

        # Build with compose
        build_args = ["build", "sensor-simulator"]

        # Add push flag if not skipping
        if not self.skip_push:
            build_args.append("--push")

        # Add no-cache flag if requested
        if not self.build_cache:
            build_args.append("--no-cache")

        # Build each tag separately (Docker Compose limitation)
        for tag in tags:
            self.env_vars["IMAGE_TAG"] = tag
            result = self._run_compose_command(
                build_args,
                check=False,
                capture_output=False,  # Show build output
                env=self.env_vars,
            )

            if result.returncode != 0:
                raise BuildError(f"Build failed for tag {tag}")

            console.print(f"[green]✓[/green] Built {tag}")

        action = "built" if self.skip_push else "built and pushed"
        console.print(f"\n[green]✓[/green] Successfully {action} all images")

        return tags

    def create_git_tag(self, version: semver.Version):
        """Create a git tag for the version"""
        if self.dev_mode:
            console.print("[dim]Skipping git tag creation in dev mode[/dim]")
            return

        tag = f"v{version}"
        console.print(f"[blue]Creating git tag {tag}...[/blue]")

        # Check if tag already exists
        result = self._run_command(["git", "tag", "--list", tag], check=False, verbose=False)

        if result.stdout.strip():
            console.print(f"[yellow]![/yellow] Tag {tag} already exists, skipping")
            return

        # Create the tag
        self._run_command(["git", "tag", tag], verbose=False)
        console.print(f"[green]✓[/green] Created git tag {tag}")

        # Push the tag if not skipping push
        if not self.skip_push:
            console.print(f"[blue]Pushing tag {tag} to remote...[/blue]")
            self._run_command(["git", "push", "origin", tag], verbose=False)
            console.print("[green]✓[/green] Pushed tag to remote")

    def write_tag_files(self, version: semver.Version, datetime_tag: str, tags: list[str]):
        """Write tag information to files"""
        console.print("[blue]Writing tag information to files...[/blue]")

        Path(".latest-image-tag").write_text(f"{datetime_tag}\n")
        Path(".latest-semver").write_text(f"{version}\n")

        # Write first tag as the main registry image
        if tags:
            Path(".latest-registry-image").write_text(f"{tags[0]}\n")

        # Write compose environment file
        env_content = []
        for key, value in self.env_vars.items():
            env_content.append(f"{key}={value}")
        Path(".env.build").write_text("\n".join(env_content) + "\n")

        console.print(f"  → .latest-image-tag: {datetime_tag}")
        console.print(f"  → .latest-semver: {version}")
        console.print(f"  → .latest-registry-image: {tags[0] if tags else 'N/A'}")
        console.print("  → .env.build: Build environment saved")

    def print_summary(self, version: semver.Version, datetime_tag: str, tags: list[str]):
        """Print build summary"""
        is_ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")

        table = Table(title="Docker Compose Build Summary", show_header=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Build System", "Docker Compose")
        table.add_row("Compose File", self.compose_file)
        table.add_row("Image Name", self.image_name)
        table.add_row("Registry", self.registry)
        table.add_row("Build Mode", "Development" if self.dev_mode else "Production")
        table.add_row("Build Type", "CI/CD" if is_ci else "Local")
        table.add_row("Semantic Version", str(version))
        table.add_row("DateTime Tag", datetime_tag)
        table.add_row("Platforms", self.platforms)
        table.add_row("Tags Created", str(len(tags)))
        table.add_row("Push Status", "Skipped" if self.skip_push else "Pushed")

        console.print(table)

        if not self.skip_push:
            console.print("\n[green]Ready to run! Copy and paste this command:[/green]\n")

            # Use appropriate tag based on build type
            tag_to_use = "dev" if self.dev_mode else "latest"

            console.print("[dim]# Run with Docker Compose:[/dim]")
            console.print("docker compose up -d")

            console.print("\n[dim]# Or run with Docker directly:[/dim]")
            run_cmd = f"""docker run --rm \\
  --name sensor-log-generator \\
  -v "$(pwd)/data":/app/data \\
  -v "$(pwd)/config":/app/config \\
  -e CONFIG_FILE=/app/config/config.yaml \\
  -e IDENTITY_FILE=/app/config/node-identity.json \\
  {self.registry}/{self.image_name}:{tag_to_use}"""
            console.print(run_cmd)

    def cleanup(self):
        """Cleanup builder if needed"""
        try:
            if hasattr(self, "builder_name") and not self.dev_mode:
                # Keep builder for future use unless explicitly removed
                pass
        except Exception:
            pass


@click.command()
@click.option("--image-name", envvar="IMAGE_NAME", help="Docker image name")
@click.option(
    "--platforms",
    envvar="PLATFORMS",
    default="linux/amd64,linux/arm64",
    help="Target platforms (comma-separated)",
)
@click.option("--dockerfile", envvar="DOCKERFILE", default="Dockerfile", help="Path to Dockerfile")
@click.option("--registry", envvar="REGISTRY", default="ghcr.io", help="Docker registry")
@click.option("--version-tag", envvar="VERSION_TAG", help="Explicit version to use (e.g., 1.2.3)")
@click.option(
    "--version-bump",
    envvar="VERSION_BUMP",
    type=click.Choice(["major", "minor", "patch"]),
    default="minor",
    help="Version bump type",
)
@click.option(
    "--dev/--prod",
    "dev_mode",
    envvar="DEV_MODE",
    default=False,
    help="Build in development mode (faster, single platform)",
)
@click.option(
    "--skip-push/--push", envvar="SKIP_PUSH", default=False, help="Skip pushing to registry"
)
@click.option("--no-cache", is_flag=True, envvar="NO_CACHE", help="Disable build cache")
@click.option("--no-login", is_flag=True, envvar="NO_LOGIN", help="Skip Docker registry login")
@click.option(
    "--compose-file",
    envvar="COMPOSE_FILE",
    default="docker-compose.build.yml",
    help="Docker Compose file for building",
)
def main(
    image_name: Optional[str],
    platforms: str,
    dockerfile: str,
    registry: str,
    version_tag: Optional[str],
    version_bump: str,
    dev_mode: bool,
    skip_push: bool,
    no_cache: bool,
    no_login: bool,
    compose_file: str,
):
    """
    Build and push multi-platform Docker images using Docker Compose.

    This script uses Docker Compose for orchestrating multi-platform builds
    with proper semantic versioning, caching, and registry management.

    Examples:
        # Production build with auto version bump
        ./build.py

        # Development build (local only, single platform)
        ./build.py --dev --skip-push

        # Build specific version
        ./build.py --version-tag 2.0.0

        # Build for specific platforms
        ./build.py --platforms linux/amd64
    """

    console.print("\n[bold blue]🐳 Docker Compose Multi-Platform Builder[/bold blue]")
    console.print("[dim]Using Docker Compose for orchestrated builds[/dim]")

    builder = DockerComposeBuilder(
        image_name=image_name,
        platforms=platforms,
        dockerfile=dockerfile,
        registry=registry,
        builder_name="multiarch-builder",
        skip_push=skip_push,
        build_cache=not no_cache,
        require_login=not no_login,
        compose_file=compose_file,
        dev_mode=dev_mode,
    )

    try:
        # Validate requirements
        builder.validate_requirements()

        # Check Docker login if needed
        if not skip_push:
            builder.check_docker_login()

        # Setup buildx builder
        builder.setup_buildx_builder()

        # Determine version
        if version_tag:
            # Use explicit version
            version = builder.parse_version(version_tag)
            console.print(f"[blue]Using explicit version: {version}[/blue]")
        else:
            # Get current version and bump
            current_version = builder.get_current_version()
            if current_version:
                console.print(f"[blue]Current version: {current_version}[/blue]")
            else:
                console.print("[blue]No existing version found, starting at 1.0.0[/blue]")

            version = builder.bump_version(current_version, version_bump)
            console.print(f"[blue]New version ({version_bump} bump): {version}[/blue]")

        # Generate datetime tag
        datetime_tag = datetime.now().strftime("%y%m%d%H%M")

        # Prepare build environment
        tags = builder.prepare_build_env(version, datetime_tag)

        # Build and push with Docker Compose
        tags = builder.build_and_push_with_compose(version, datetime_tag, tags)

        # Create git tag
        if not skip_push and not dev_mode:
            builder.create_git_tag(version)

        # Write tag files
        builder.write_tag_files(version, datetime_tag, tags)

        # Print summary
        builder.print_summary(version, datetime_tag, tags)

        console.print("\n[bold green]✓ Build completed successfully![/bold green]")

    except BuildError as e:
        console.print(f"\n[bold red]✗ Build failed:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Build cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}")
        sys.exit(1)
    finally:
        builder.cleanup()


if __name__ == "__main__":
    main()
