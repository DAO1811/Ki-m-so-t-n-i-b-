"""Conservative resource checks for optional inference in a shared web service."""

from pathlib import Path

MIB = 1024 * 1024
START_HEADROOM = 300 * MIB
RUN_HEADROOM = 64 * MIB


def remaining_memory():
    """Use the smallest known host/container allowance; never assume host RAM."""
    remaining = []
    for limit_path, usage_path in (
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
        (
            "/sys/fs/cgroup/memory/memory.limit_in_bytes",
            "/sys/fs/cgroup/memory/memory.usage_in_bytes",
        ),
    ):
        try:
            limit = int(Path(limit_path).read_text().strip())
            usage = int(Path(usage_path).read_text().strip())
            if 0 < limit < 1 << 60 and usage >= 0:
                remaining.append(max(0, limit - usage))
        except (OSError, ValueError):
            continue
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if parts[0] == "MemAvailable:" and len(parts) == 3 and parts[2] == "kB":
                remaining.append(max(0, int(parts[1])) * 1024)
                break
    except (OSError, ValueError, IndexError):
        pass
    return min(remaining) if remaining else None
