# newapp — sysinfo CLI

A colorized, terminal-friendly system-information tool written in Python.

## Features

- OS version, Python version
- CPU usage (overall + per-core), with green/yellow/red threshold colouring
- Memory usage with used / free / total breakdown (MB or GB)
- Per-mount-point disk usage
- Top-N processes by CPU %
- `--json` flag for machine-readable output
- Respects the [`NO_COLOR`](https://no-color.org/) environment variable

## Installation

```bash
# From the project root — editable install (recommended for development)
pip install -e .

# Or install directly
pip install .
```

## Usage

```bash
# Default output (all sections)
sysinfo

# Show top 5 processes instead of 10
sysinfo --top 5

# Suppress process list
sysinfo --top 0

# JSON full snapshot (python_version, cpu, memory, disk, top_processes)
sysinfo --json

# Print only the Python interpreter version
sysinfo --python-version
```

### Example output

```
OS Version:     macOS 14.4 (Darwin 23.4.0)
Python:         3.12.3
CPU Usage:      12.4%
  Core 0:       8.1%
  Core 1:       15.2%
  ...
Memory Usage:   48.2%  (7.7 GB used / 8.3 GB free / 16.0 GB total)
Disk Usage:
  /:            58.6% (269.2 / 460.4 GiB, 191.2 GiB free)

Top 10 Processes (by CPU%):
      PID  Name                   CPU%     MEM%
     1234  Safari                  9.8%    2.1%
```

## Development

```bash
# Install in editable mode with test dependencies
pip install -e .
pip install pytest flake8

# Run tests
python -m pytest

# Lint
flake8 sysinfo.py tests/
```

## Dependencies

| Package    | Purpose                            |
|------------|------------------------------------|
| `colorama` | Cross-platform ANSI colour support |
| `psutil`   | CPU, memory, disk, process metrics |
