# Quick Command Reference

## Essential Commands

### Testing
```bash
just test-quick      # Quick tests with 2s timeout (~10 seconds)
just test-fast       # Subset of important tests (~30 seconds)
just test           # All tests with standard timeout (~2 minutes)
just test-coverage  # Run tests with coverage report
```

### Code Quality
```bash
just lint           # Check code style issues
just lint-fix       # Auto-fix code style issues
just type-check     # Run mypy type checking
just check-all      # Run ALL checks (lint, type, tests)
just check-quick    # Quick check (lint + type only, no tests)
```

### Development
```bash
just run            # Run the application
just debug          # Run with debug logging
just monitor-db     # Monitor database in real-time
just clean          # Clean generated files
```

### Docker
```bash
just docker-build   # Build Docker image
just docker-run     # Run container (Linux)
just docker-run-delete  # Run container (Mac/Windows)
```

## Common Workflows

### Before Committing Code
```bash
# Option 1: Run everything
just check-all

# Option 2: Quick checks only
just check-quick
just test-quick

# Option 3: Fix issues automatically
just check-fix
```

### Debugging Test Failures
```bash
# Run specific test file
just test-file tests/test_database.py

# Run tests serially to avoid database locks
just test-serial

# Check recent errors
just show-errors
```

### Database Inspection
```bash
just db-stats       # Show reading count
just db-read        # Open SQLite in read-only mode
just check-db       # Check database integrity
```

## Installation & Setup

### First Time Setup
```bash
# Install dependencies and setup pre-commit hooks
just setup-dev
```

### Update Dependencies
```bash
just update
```

### Clean Everything
```bash
just clean          # Clean caches and generated files
just clean-all      # Also remove virtual environment
```

## Advanced Commands

### Performance Testing
```bash
just stress-test       # Run stress test
just stress-test-prod  # Production stress test
just profile          # Profile with py-spy (requires py-spy)
```

### Continuous Development
```bash
just watch-tests    # Auto-run tests on file changes (requires entr)
just watch-check    # Auto-run checks on file changes (requires entr)
just tail-logs      # Follow application logs
```

### Git Integration
```bash
just commit "message"           # Commit with pre-commit hooks
just commit-no-verify "message" # Bypass hooks (use sparingly!)
just pre-commit                 # Run pre-commit on all files
```

## Tips

1. **Use `just` alone to see all available commands**
2. **Start with `just test-quick` for rapid feedback**
3. **Run `just check-all` before pushing code**
4. **Use `just debug` when troubleshooting issues**
5. **Run `just setup-dev` after cloning the repository**

## Required Tools

- **uv**: Python package manager (required)
- **just**: Command runner (required)
- **entr**: File watcher (optional, for watch commands)
- **py-spy**: Python profiler (optional, for profiling)

## Installing just

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin

# Or via cargo
cargo install just
```