# Container Build Strategy

## Overview
This document describes the container build and release strategy for the sensor-log-generator project.

## Build Environments

### 1. Local Development Builds
When building locally (not in CI), containers are automatically tagged with development tags:
- `image:dev` - Latest development build
- `image:dev-YYYYMMDDHHMMSS` - Timestamped development build
- `image:VERSION-dev` - Version-specific development build

**To build locally:**
```bash
# Build with automatic dev tags
uv run build.py --skip-push

# Or build and push to registry
uv run build.py
```

### 2. CI/CD Pipeline
The CI pipeline (`ci.yml`) runs on pushes and pull requests but **does NOT build containers**.
It only:
- Runs linting and type checking
- Executes the test suite
- Validates the Dockerfile syntax

### 3. Release Builds
Release builds are triggered automatically when a git tag is pushed (format: `v*`).

**To create a release:**
```bash
# Create and push a tag
git tag v1.2.3
git push origin v1.2.3
```

The release workflow will:
1. Run all tests
2. Build multi-platform containers (linux/amd64, linux/arm64)
3. Push containers with multiple tags:
   - `image:latest`
   - `image:v1.2.3`
   - `image:v1.2` (minor version)
   - `image:v1` (major version)
4. Generate automatic changelog from commit history
5. Create GitHub release with:
   - Changelog
   - SBOM (Software Bill of Materials)
   - Container signatures (Cosign/Sigstore)

## Tagging Strategy

### Development Tags (Local Builds)
- `dev` - Always points to the latest local build
- `dev-YYYYMMDDHHMMSS` - Unique timestamp for each build
- `VERSION-dev` - Development version of a specific release

### Production Tags (Release Builds)
- `latest` - Always points to the latest stable release
- `vX.Y.Z` - Specific version (immutable)
- `vX.Y` - Minor version (updates with patches)
- `vX` - Major version (updates with minor/patch releases)
- `YYMMDDHHM` - DateTime tag for tracking
- `GIT_HASH` - Short git commit hash

## Changelog Generation

The release workflow automatically generates a changelog that includes:
- **Features** (`feat:` commits)
- **Bug Fixes** (`fix:` commits)
- **Documentation** (`docs:` commits)
- **Performance** (`perf:` commits)
- **Other Changes** (all other commits)
- **Contributors** list
- **Statistics** (commit count, files changed)

## Best Practices

### For Developers
1. Build locally during development - containers will be tagged with `dev`
2. Use conventional commits for better changelogs:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `perf:` for performance improvements
   - `chore:` for maintenance tasks

### For Releases
1. Ensure all tests pass before tagging
2. Use semantic versioning (MAJOR.MINOR.PATCH)
3. Tag format must be `vX.Y.Z` (e.g., `v1.2.3`)
4. Pre-releases can use suffixes: `v1.2.3-beta.1`, `v1.2.3-rc.1`

### CI/CD Flow
```
Developer Push → CI Tests → ✓ (No container build)
                           ↓
                    Tag Push (v*) → Release Workflow → Multi-platform Build → Push to Registry
                                                      ↓
                                                GitHub Release with Changelog
```

## Manual Release (Alternative)

You can also trigger a release manually from GitHub Actions:
1. Go to Actions → Release workflow
2. Click "Run workflow"
3. Enter version number (e.g., `1.2.3`)
4. The workflow will create the tag and release

## Environment Variables

- `CI=true` - Set automatically in GitHub Actions
- `GITHUB_ACTIONS=true` - Set automatically in GitHub Actions
- These variables control whether development or production tags are used

## Security

- All release containers are signed with Cosign/Sigstore
- SBOM is generated for supply chain transparency
- Container registry requires authentication for pushes
- GitHub Actions uses GITHUB_TOKEN for registry authentication