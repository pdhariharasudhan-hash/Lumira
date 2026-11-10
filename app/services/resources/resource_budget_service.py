"""Resource-aware execution guidance for memory-constrained Lumira hosts.

This service reports measurements only when an installed provider can supply them.
It does not kill processes, change Windows settings, or claim to enforce concurrency.
"""
from __future__ import annotations

import os
from typing import Any


class ResourceBudgetService:
    """Produce a conservative, RAM-aware execution profile without hard dependencies."""

    DEFAULT_LOCAL_RAM_GB = 8.0

    def snapshot(self) -> dict[str, Any]:
        memory: dict[str, Any] = {
            "available": False,
            "source": "unavailable",
            "total_gib": None,
            "available_gib": None,
            "used_percent": None,
            "process_rss_mib": None,
        }
        try:
            import psutil  # type: ignore[import-not-found]

            vm = psutil.virtual_memory()
            process = psutil.Process(os.getpid())
            memory.update({
                "available": True,
                "source": "psutil",
                "total_gib": round(vm.total / (1024 ** 3), 2),
                "available_gib": round(vm.available / (1024 ** 3), 2),
                "used_percent": float(vm.percent),
                "process_rss_mib": round(process.memory_info().rss / (1024 ** 2), 1),
            })
        except Exception:
            # Windows has a built-in RAM API, so telemetry still works without psutil.
            try:
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                status = MEMORYSTATUSEX()
                status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    memory.update({
                        "available": True,
                        "source": "windows_global_memory_status",
                        "total_gib": round(status.ullTotalPhys / (1024 ** 3), 2),
                        "available_gib": round(status.ullAvailPhys / (1024 ** 3), 2),
                        "used_percent": float(status.dwMemoryLoad),
                    })
            except Exception:
                # Resource visibility is optional; it must never prevent Lumira from working.
                pass

        # WSL and Linux hosts do not expose the Windows memory API. Read the
        # kernel's procfs counters as a dependency-free fallback when psutil is
        # unavailable, so RAM-aware guards still work on portable deployments.
        if not memory["available"] and os.name != "nt":
            try:
                meminfo: dict[str, int] = {}
                with open("/proc/meminfo", "r", encoding="ascii") as handle:
                    for line in handle:
                        key, separator, remainder = line.partition(":")
                        if not separator or key not in {"MemTotal", "MemAvailable"}:
                            continue
                        parts = remainder.split()
                        if parts:
                            meminfo[key] = int(parts[0]) * 1024

                total_bytes = meminfo.get("MemTotal", 0)
                available_bytes = meminfo.get("MemAvailable", 0)
                if total_bytes > 0 and 0 <= available_bytes <= total_bytes:
                    memory.update({
                        "available": True,
                        "source": "proc_meminfo",
                        "total_gib": round(total_bytes / (1024 ** 3), 2),
                        "available_gib": round(available_bytes / (1024 ** 3), 2),
                        "used_percent": round(
                            (1 - available_bytes / total_bytes) * 100,
                            1,
                        ),
                    })
                    try:
                        with open("/proc/self/status", "r", encoding="ascii") as handle:
                            for line in handle:
                                if line.startswith("VmRSS:"):
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        memory["process_rss_mib"] = round(
                                            int(parts[1]) / 1024,
                                            1,
                                        )
                                    break
                    except (OSError, ValueError):
                        # Process RSS is optional; system RAM telemetry remains useful.
                        pass
            except (OSError, ValueError):
                # Telemetry remains best-effort if procfs is unavailable or malformed.
                pass

        configured_gib = self._configured_ram_gib()
        total_gib = memory.get("total_gib") or configured_gib
        available_gib = memory.get("available_gib")
        used_percent = memory.get("used_percent")
        if isinstance(available_gib, (int, float)) and total_gib:
            available_ratio = available_gib / total_gib
            if available_ratio < 0.12:
                pressure = "critical"
            elif available_ratio < 0.22:
                pressure = "constrained"
            else:
                pressure = "normal"
        elif isinstance(used_percent, (int, float)):
            pressure = "critical" if used_percent >= 90 else "constrained" if used_percent >= 80 else "unknown"
        else:
            pressure = "unknown"

        low_memory_host = total_gib <= 8.5
        policy = {
            "profile": "low_memory" if low_memory_host else "standard",
            "max_concurrent_local_model_requests": 1,
            "max_concurrent_agents": 1 if low_memory_host or pressure in {"critical", "constrained"} else 2,
            "max_provider_files": 6 if low_memory_host else 12,
            "max_context_characters": 30000 if low_memory_host else 60000,
            "max_file_characters": 12000 if low_memory_host else 24000,
            "prefer_streaming_and_incremental_results": True,
            "avoid_loading_multiple_local_models": True,
            "defer_optional_heavy_media_work_when_under_pressure": pressure in {"critical", "constrained"},
            "enforcement": "partially_enforced_by_selected_consumers",
        }
        return {
            "memory": memory,
            "resource_pressure": pressure,
            "policy": policy,
            "notes": [
                "RAM measurements use psutil when available, with Windows native and Linux/WSL procfs fallbacks; telemetry can still be unavailable.",
                "Selected consumers enforce provider context limits and defer image generation/analysis plus speech synthesis/transcription under memory pressure; global concurrency limits remain advisory.",
                "No processes are terminated and no operating-system settings are changed.",
            ],
        }

    @classmethod
    def _configured_ram_gib(cls) -> float:
        raw = os.getenv("LUMIRA_HOST_RAM_GIB", "")
        try:
            value = float(raw)
            return value if 1 <= value <= 1024 else cls.DEFAULT_LOCAL_RAM_GB
        except (TypeError, ValueError):
            return cls.DEFAULT_LOCAL_RAM_GB

    def execution_guidance(self) -> dict[str, Any]:
        result = self.snapshot()
        policy = result["policy"]
        return {
            "resource_profile": policy["profile"],
            "resource_pressure": result["resource_pressure"],
            "max_concurrent_agents": policy["max_concurrent_agents"],
            "max_concurrent_local_model_requests": policy["max_concurrent_local_model_requests"],
            "max_provider_files": policy["max_provider_files"],
            "max_context_characters": policy["max_context_characters"],
            "max_file_characters": policy["max_file_characters"],
            "avoid_loading_multiple_local_models": policy["avoid_loading_multiple_local_models"],
            "defer_optional_heavy_media_work": policy["defer_optional_heavy_media_work_when_under_pressure"],
        }
