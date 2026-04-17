[PRD]
# PRD: Developer System Insight CLI Tool

## Overview

A Python CLI tool that gives developers on-demand snapshots of local machine system metrics — CPU usage, memory, disk, and top processes — along with the current Python version. The tool is installable via `pip` and supports JSON output via a flag for pipeline integration.

## Goals

- Provide developers with instant, readable system health snapshots from the terminal
- Surface CPU, memory, disk, and top-process data in a single command
- Display the current Python version in plaintext
- Support JSON output format for scripting and toolchain integration
- Be installable as a standard Python package via `pip install`

## Quality Gates

These commands must pass for every user story:

- `pytest` — Unit and integration tests
- `flake8` — Code style linting

## User Stories

### US-001: Display Python version

**Description:** As a developer, I want the tool to print the current Python version in plaintext so that I can quickly confirm my runtime environment.

**Acceptance Criteria:**

- [ ] Running `sysinfo --python-version` (or `sysinfo version`) prints the Python version string (e.g. `Python 3.11.4`) to stdout
- [ ] Output is plaintext, one line
- [ ] Exit code is 0 on success

### US-002: Snapshot CPU usage

**Description:** As a developer, I want to see current CPU usage so that I can identify if my machine is under heavy load.

**Acceptance Criteria:**

- [ ] Default text output shows overall CPU % and per-core %
- [ ] Values are human-readable (e.g. `CPU: 42.3% overall | Core 0: 38% | Core 1: 47%`)
- [ ] JSON output (`--json` flag) returns structured data: `{"cpu": {"overall": 42.3, "cores": [...]}}`

### US-003: Snapshot memory usage

**Description:** As a developer, I want to see memory usage so that I can detect memory pressure on my machine.

**Acceptance Criteria:**

- [ ] Default text output shows used, free, and cached memory in human-readable units (MB/GB)
- [ ] JSON output (`--json` flag) returns `{"memory": {"used_mb": ..., "free_mb": ..., "cached_mb": ..., "total_mb": ...}}`
- [ ] Percentage used is shown in text output

### US-004: Snapshot disk usage

**Description:** As a developer, I want to see disk usage per mount point so that I can spot full or nearly-full volumes.

**Acceptance Criteria:**

- [ ] Default text output lists each mount point with used/total/free and percent used
- [ ] JSON output (`--json` flag) returns `{"disk": [{"mount": "/", "used_gb": ..., "free_gb": ..., "total_gb": ..., "percent": ...}, ...]}`
- [ ] Covers all mounted filesystems on the local machine

### US-005: Show top processes by resource consumption

**Description:** As a developer, I want to see the top processes consuming CPU and memory so that I can identify resource hogs.

**Acceptance Criteria:**

- [ ] Default text output shows top 10 processes sorted by CPU % with columns: PID, name, CPU%, MEM%
- [ ] JSON output (`--json` flag) returns `{"top_processes": [{"pid": ..., "name": "...", "cpu_percent": ..., "mem_percent": ...}, ...]}`
- [ ] Number of processes shown is configurable via `--top N` flag (default 10)

### US-006: Full system snapshot command

**Description:** As a developer, I want a single command that shows all metrics at once so that I get a complete system overview instantly.

**Acceptance Criteria:**

- [ ] Running `sysinfo` (no subcommand) outputs Python version, CPU, memory, disk, and top processes in sequence
- [ ] `--json` flag outputs a single JSON object containing all metric sections
- [ ] Exit code is 0 on success, non-zero on failure

### US-007: pip-installable package

**Description:** As a developer, I want to install the tool with `pip install` so that I can use it anywhere without manual setup.

**Acceptance Criteria:**

- [ ] `pyproject.toml` (or `setup.py`) defines the package with entry point `sysinfo`
- [ ] After `pip install .`, running `sysinfo` from the terminal works
- [ ] Package declares all dependencies (e.g. `psutil`)
- [ ] Package includes a `README` with install and usage instructions

## Functional Requirements

- FR-1: The CLI entry point must be named `sysinfo`
- FR-2: A `--json` flag must switch all output to machine-readable JSON
- FR-3: CPU metrics must be collected using `psutil.cpu_percent(percpu=True)`
- FR-4: Memory metrics must use `psutil.virtual_memory()`
- FR-5: Disk metrics must use `psutil.disk_partitions()` and `psutil.disk_usage()`
- FR-6: Process list must use `psutil.process_iter()` sorted by CPU %
- FR-7: Python version must be sourced from `sys.version` or `platform.python_version()`
- FR-8: Non-zero exit code must be returned on any unhandled error

## Non-Goals

- Real-time / live-updating dashboard (no curses/TUI interface)
- Remote server or SSH monitoring
- Network activity or connection metrics
- Container or Kubernetes metrics
- Alert thresholds or notifications
- Historical data storage or trending

## Technical Considerations

- Use `psutil` as the primary system metrics library
- Python 3.9+ compatibility recommended
- Package entry point defined via `pyproject.toml` `[project.scripts]`
- Tests should assert on stdout using `subprocess` or `click.testing.CliRunner`
- Consider `click` or `argparse` for CLI argument handling
- `flake8` config (`.flake8` or `setup.cfg`) should be committed with max-line-length set appropriately

## Success Metrics

- All 7 user stories pass `pytest && flake8` with no errors
- `sysinfo` command runs in under 2 seconds on a standard laptop
- JSON output is valid and parseable by `jq` or Python `json.loads()`
- Package installs cleanly in a fresh virtualenv

## Open Questions

- Should `sysinfo` support subcommands (e.g. `sysinfo cpu`, `sysinfo memory`) in addition to the all-in-one default?
- Should there be a `--top N` global flag or only on the processes subcommand?
- Any preference for `click` vs `argparse` for the CLI framework?
[/PRD]
