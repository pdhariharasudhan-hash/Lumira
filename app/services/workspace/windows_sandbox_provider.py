from __future__ import annotations

import csv
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class WindowsSandboxProvider:
    """Disposable Windows Sandbox runner for bounded generated-project checks.

    Only a temporary snapshot of the project is writable inside the guest.
    The original project, runtime, and control script are mapped read-only.
    Networking, clipboard, audio/video input, printer redirection, and vGPU
    are disabled. The guest always shuts itself down after reporting a result.
    """

    MEMORY_MB = 2048
    MAX_PROJECT_BYTES = 250 * 1024 * 1024
    MAX_PROJECT_FILES = 5000
    MAX_OUTPUT_CHARS = 20_000
    MAX_RESULT_BYTES = 64 * 1024
    STARTUP_GRACE_SECONDS = 90
    SHUTDOWN_GRACE_SECONDS = 30
    EXCLUDED_DIRS = {
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    }
    SECRET_NAMES = {
        "id_rsa", "id_ed25519", "credentials.json", "secrets.json",
        "service-account.json",
    }
    COMMANDS = {
        "pytest": ("python", "-m", "pytest", "-q"),
        "compileall": ("python", "-m", "compileall", "app"),
        "npm_test": ("npm", "test", "--", "--run"),
        "npm_build": ("npm", "run", "build"),
    }
    _run_lock = threading.Lock()

    def __init__(self, *, memory_mb: int = MEMORY_MB):
        if memory_mb < 2048 or memory_mb > 4096:
            raise ValueError("Windows Sandbox memory must be between 2048 and 4096 MB")
        self.memory_mb = memory_mb

    @staticmethod
    def _sandbox_executable() -> Path:
        return Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsSandbox.exe"

    @staticmethod
    def _dism_executable() -> str | None:
        return shutil.which("dism.exe") or shutil.which("dism")

    def status(self):
        from app.services.workspace.container_sandbox_provider import SandboxStatus

        if sys.platform != "win32":
            return SandboxStatus(False, None, "windows_sandbox_requires_windows")
        executable = self._sandbox_executable()
        if not executable.is_file():
            return SandboxStatus(False, None, "windows_sandbox_not_installed")
        dism = self._dism_executable()
        if not dism:
            return SandboxStatus(False, "windows_sandbox", "windows_feature_check_unavailable")
        try:
            result = subprocess.run(
                [dism, "/online", "/Get-FeatureInfo", "/FeatureName:Containers-DisposableClientVM"],
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return SandboxStatus(False, "windows_sandbox", "windows_feature_check_failed")
        if result.returncode != 0:
            return SandboxStatus(False, "windows_sandbox", "windows_feature_check_failed")
        import re

        if not re.search(r"State\s*:\s*Enabled", result.stdout, re.IGNORECASE):
            return SandboxStatus(False, "windows_sandbox", "windows_sandbox_feature_disabled")
        return SandboxStatus(True, "windows_sandbox", "verified")

    @classmethod
    def _is_sensitive(cls, name: str) -> bool:
        lowered = name.lower()
        return (
            lowered in cls.SECRET_NAMES
            or lowered.startswith(".env")
            or lowered.endswith((".pem", ".key", ".pfx", ".p12"))
        )

    @classmethod
    def _validate_project_tree(cls, source: Path) -> tuple[int, int]:
        total_bytes = 0
        total_files = 0
        for current, dirs, files in os.walk(source, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if name.lower() not in cls.EXCLUDED_DIRS]
            for name in list(dirs) + files:
                if cls._is_sensitive(name):
                    if name in dirs:
                        dirs.remove(name)
                    continue
                item = current_path / name
                info = item.lstat()
                attributes = getattr(info, "st_file_attributes", 0)
                reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
                if stat.S_ISLNK(info.st_mode) or reparse:
                    raise ValueError("Project contains a symbolic link or reparse point")
                if name in dirs:
                    if not stat.S_ISDIR(info.st_mode):
                        raise ValueError("Project contains an unsupported filesystem entry")
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("Project contains a non-regular file")
                total_files += 1
                total_bytes += info.st_size
                if total_files > cls.MAX_PROJECT_FILES or total_bytes > cls.MAX_PROJECT_BYTES:
                    raise ValueError("Project snapshot exceeds the sandbox size limits")
        return total_files, total_bytes

    @classmethod
    def _copy_snapshot(cls, source: Path, destination: Path) -> None:
        cls._validate_project_tree(source)

        def ignore(_directory: str, names: list[str]) -> set[str]:
            return {
                name for name in names
                if name.lower() in cls.EXCLUDED_DIRS or cls._is_sensitive(name)
            }

        shutil.copytree(source, destination, ignore=ignore, symlinks=False)

    @staticmethod
    def _grant_host_folder_access(root: Path) -> None:
        """Make the disposable staging tree readable to the current host identity.

        tempfile.mkdtemp may create a restrictive ACL without the interactive
        user SID. Windows Sandbox cannot map such a folder even though the
        owner belongs to Administrators, so grant only the current user access
        to this disposable tree before exposing it to the guest.
        """
        whoami = shutil.which("whoami.exe") or shutil.which("whoami")
        icacls = shutil.which("icacls.exe") or shutil.which("icacls")
        if not whoami or not icacls:
            raise RuntimeError("sandbox_temp_acl_tools_unavailable")
        identity = subprocess.run(
            [whoami], capture_output=True, text=True, timeout=5, shell=False
        )
        user = identity.stdout.strip()
        if identity.returncode != 0 or not user or "\n" in user or "\r" in user:
            raise RuntimeError("sandbox_host_identity_unavailable")
        result = subprocess.run(
            [icacls, str(root), "/inheritance:e", "/grant", f"{user}:(OI)(CI)F", "/T", "/C"],
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError("sandbox_temp_acl_setup_failed")

    @staticmethod
    def _guest_script() -> str:
        return r"""$ErrorActionPreference = 'Stop'
$requestPath = 'C:\LumiraControl\request.json'
$resultPath = 'C:\LumiraResult\result.json'
$request = $null
$result = $null
$jobHandle = [IntPtr]::Zero
$jobLimitsApplied = $false
$jobSource = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class LumiraJob {
    [StructLayout(LayoutKind.Sequential)]
    private struct BasicLimitInformation {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct IoCounters {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct ExtendedLimitInformation {
        public BasicLimitInformation BasicLimitInformation;
        public IoCounters IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct CpuRateControlInformation {
        public uint ControlFlags;
        public uint CpuRate;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    public static IntPtr CreateAndAssignCurrentProcess() {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try {
            ExtendedLimitInformation limits = new ExtendedLimitInformation();
            limits.BasicLimitInformation.LimitFlags = 0x8 | 0x100 | 0x200 | 0x2000;
            limits.BasicLimitInformation.ActiveProcessLimit = 64;
            limits.ProcessMemoryLimit = new UIntPtr(768UL * 1024UL * 1024UL);
            limits.JobMemoryLimit = new UIntPtr(1024UL * 1024UL * 1024UL);
            int size = Marshal.SizeOf(typeof(ExtendedLimitInformation));
            IntPtr buffer = Marshal.AllocHGlobal(size);
            try {
                Marshal.StructureToPtr(limits, buffer, false);
                if (!SetInformationJobObject(job, 9, buffer, (uint)size))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
            } finally { Marshal.FreeHGlobal(buffer); }

            CpuRateControlInformation cpu = new CpuRateControlInformation();
            cpu.ControlFlags = 0x1 | 0x4;
            cpu.CpuRate = 5000;
            size = Marshal.SizeOf(typeof(CpuRateControlInformation));
            buffer = Marshal.AllocHGlobal(size);
            try {
                Marshal.StructureToPtr(cpu, buffer, false);
                if (!SetInformationJobObject(job, 15, buffer, (uint)size))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
            } finally { Marshal.FreeHGlobal(buffer); }

            if (!AssignProcessToJobObject(job, GetCurrentProcess()))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            return job;
        } catch {
            CloseHandle(job);
            throw;
        }
    }
    public static void Close(IntPtr job) {
        if (job != IntPtr.Zero) CloseHandle(job);
    }
}
'@
try {
    $request = Get-Content -LiteralPath $requestPath -Raw | ConvertFrom-Json
    Add-Type -TypeDefinition $jobSource
    $jobHandle = [LumiraJob]::CreateAndAssignCurrentProcess()
    $jobLimitsApplied = $true
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.WorkingDirectory = 'C:\LumiraProject'
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    switch ($request.command_id) {
        'pytest' {
            $psi.FileName = 'C:\LumiraPython\python.exe'
            $psi.Arguments = '-m pytest -q'
            $psi.EnvironmentVariables['PYTHONHOME'] = 'C:\LumiraPython'
            $psi.EnvironmentVariables['PYTHONPATH'] = 'C:\LumiraSitePackages'
        }
        'compileall' {
            $psi.FileName = 'C:\LumiraPython\python.exe'
            $psi.Arguments = '-m compileall app'
            $psi.EnvironmentVariables['PYTHONHOME'] = 'C:\LumiraPython'
            $psi.EnvironmentVariables['PYTHONPATH'] = 'C:\LumiraSitePackages'
        }
        'npm_test' {
            $psi.FileName = 'C:\LumiraNode\node.exe'
            $psi.Arguments = 'C:\LumiraNode\node_modules\npm\bin\npm-cli.js test -- --run'
            $psi.EnvironmentVariables['PATH'] = 'C:\LumiraNode;' + $psi.EnvironmentVariables['PATH']
        }
        'npm_build' {
            $psi.FileName = 'C:\LumiraNode\node.exe'
            $psi.Arguments = 'C:\LumiraNode\node_modules\npm\bin\npm-cli.js run build'
            $psi.EnvironmentVariables['PATH'] = 'C:\LumiraNode;' + $psi.EnvironmentVariables['PATH']
        }
        default { throw 'unsupported_command' }
    }
    $started = [DateTime]::UtcNow
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $timedOut = -not $process.WaitForExit([int]$request.timeout_seconds * 1000)
    if ($timedOut) {
        & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        if (-not $process.HasExited) { $process.Kill() }
    }
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    if ($stdout.Length -gt 20000) { $stdout = $stdout.Substring(0, 20000) }
    if ($stderr.Length -gt 20000) { $stderr = $stderr.Substring(0, 20000) }
    $result = [ordered]@{
        nonce = [string]$request.nonce
        identity = (whoami)
        job_limits_applied = [bool]$jobLimitsApplied
        exit_code = [int]$process.ExitCode
        timed_out = [bool]$timedOut
        stdout = $stdout
        stderr = $stderr
        elapsed_ms = [int]([DateTime]::UtcNow - $started).TotalMilliseconds
    }
} catch {
    $nonce = if ($request -and $request.nonce) { [string]$request.nonce } else { '' }
    $result = [ordered]@{
        nonce = $nonce
        identity = (whoami)
        job_limits_applied = [bool]$jobLimitsApplied
        bootstrap_error = $_.Exception.GetType().Name
        exit_code = 125
        timed_out = $false
        stdout = ''
        stderr = 'Sandbox guest could not start the requested validation command.'
        elapsed_ms = 0
    }
}
$json = ConvertTo-Json -InputObject $result -Compress -Depth 5
[System.IO.File]::WriteAllText($resultPath, $json, (New-Object System.Text.UTF8Encoding($false)))
shutdown.exe /s /t 0
if ($jobHandle -ne [IntPtr]::Zero) { [LumiraJob]::Close($jobHandle) }
"""

    @staticmethod
    def _process_ids(image_name: str) -> set[int]:
        tasklist = shutil.which("tasklist.exe") or shutil.which("tasklist")
        if not tasklist:
            return set()
        try:
            result = subprocess.run(
                [tasklist, "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
        values: set[int] = set()
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) >= 2 and row[0].lower().startswith(image_name.lower()):
                try:
                    values.add(int(row[1]))
                except ValueError:
                    pass
        return values

    @classmethod
    def _vmmem_pids(cls) -> set[int]:
        return cls._process_ids("vmmemWindowsSandbox")

    @classmethod
    def _session_pids(cls) -> set[int]:
        return cls._process_ids("WindowsSandboxRemoteSession")

    @staticmethod
    def _acquire_process_lock(lock_path: Path | None = None):
        path = lock_path or (Path(tempfile.gettempdir()) / "lumira-windows-sandbox-provider.lock")
        handle = path.open("a+b")
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except (OSError, ImportError):
            handle.close()
            raise RuntimeError("windows_sandbox_busy")

    @staticmethod
    def _release_process_lock(handle) -> None:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, ImportError):
            pass
        finally:
            handle.close()

    @staticmethod
    def _stop_processes(pids: set[int]) -> None:
        taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
        if not taskkill:
            return
        for pid in pids:
            subprocess.run(
                [taskkill, "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )

    @staticmethod
    def _write_wsb(
        config_path: Path,
        control: Path,
        project: Path,
        output: Path,
        python_home: Path,
        python_site: Path,
        node_home: Path | None,
        memory_mb: int,
    ) -> None:
        root = ET.Element("Configuration")
        settings = {
            "VGpu": "Disable",
            "Networking": "Disable",
            "AudioInput": "Disable",
            "VideoInput": "Disable",
            "ClipboardRedirection": "Disable",
            "PrinterRedirection": "Disable",
            "ProtectedClient": "Enable",
            "MemoryInMB": str(memory_mb),
        }
        for key, value in settings.items():
            ET.SubElement(root, key).text = value
        mapped = ET.SubElement(root, "MappedFolders")

        def add_mapping(host: Path, guest: str, readonly: bool) -> None:
            entry = ET.SubElement(mapped, "MappedFolder")
            ET.SubElement(entry, "HostFolder").text = str(host.resolve())
            ET.SubElement(entry, "SandboxFolder").text = guest
            ET.SubElement(entry, "ReadOnly").text = "true" if readonly else "false"

        add_mapping(control, r"C:\LumiraControl", True)
        add_mapping(project, r"C:\LumiraProject", False)
        add_mapping(python_home, r"C:\LumiraPython", True)
        if python_site.is_dir():
            add_mapping(python_site, r"C:\LumiraSitePackages", True)
        if node_home is not None and node_home.is_dir():
            add_mapping(node_home, r"C:\LumiraNode", True)
        add_mapping(output, r"C:\LumiraResult", False)
        logon = ET.SubElement(root, "LogonCommand")
        ET.SubElement(logon, "Command").text = (
            r"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\LumiraControl\run.ps1"
        )
        ET.indent(root, space="  ")
        config_path.write_text(
            ET.tostring(root, encoding="unicode"),
            encoding="utf-8",
        )

    @staticmethod
    def _safe_result(path: Path, expected_nonce: str) -> dict[str, Any]:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Sandbox result is missing or invalid")
        info = path.stat()
        attributes = getattr(info, "st_file_attributes", 0)
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise RuntimeError("Sandbox result path is not a regular file")
        if info.st_size <= 0 or info.st_size > WindowsSandboxProvider.MAX_RESULT_BYTES:
            raise RuntimeError("Sandbox result exceeds the permitted size")
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(result, dict) or result.get("nonce") != expected_nonce:
            raise RuntimeError("Sandbox result could not be correlated to this run")
        identity = result.get("identity")
        if not isinstance(identity, str) or not identity.lower().endswith(r"\wdagutilityaccount"):
            raise RuntimeError("Sandbox command did not run under the Windows Sandbox account")
        if not isinstance(result.get("exit_code"), int):
            raise RuntimeError("Sandbox returned an invalid process exit code")
        if not isinstance(result.get("timed_out"), bool):
            raise RuntimeError("Sandbox returned an invalid timeout state")
        if result.get("job_limits_applied") is not True:
            raise RuntimeError("windows_sandbox_resource_limits_unverified")
        if not isinstance(result.get("stdout"), str) or not isinstance(result.get("stderr"), str):
            raise RuntimeError("Sandbox returned invalid process output")
        return result

    def run(
        self,
        command: tuple[str, ...],
        project_path: Path,
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        command_id = next((key for key, value in self.COMMANDS.items() if tuple(command) == value), None)
        if command_id is None:
            raise ValueError("Command is not allowlisted for Windows Sandbox")
        if not isinstance(timeout, int) or timeout < 1 or timeout > 120:
            raise ValueError("Sandbox timeout must be between 1 and 120 seconds")
        source = Path(project_path).resolve(strict=True)
        if not source.is_dir():
            raise ValueError("Sandbox project path must be a directory")
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("A Windows Sandbox run is already active")
        root: Path | None = None
        process_lock_handle = None
        vm_before: set[int] = set()
        session_before: set[int] = set()
        vm_started: set[int] = set()
        session_started: set[int] = set()
        try:
            process_lock_handle = self._acquire_process_lock()
            status = self.status()
            if not status.available:
                raise RuntimeError(status.reason)
            vm_before = self._vmmem_pids()
            if vm_before:
                raise RuntimeError("windows_sandbox_busy")
            session_before = self._session_pids()
            root = Path(tempfile.mkdtemp(prefix="lumira-windows-sandbox-"))
            control = root / "control"
            staged_project = root / "project"
            output = root / "output"
            control.mkdir()
            output.mkdir()
            self._copy_snapshot(source, staged_project)
            self._grant_host_folder_access(root)

            python_home = Path(sys.base_prefix).resolve()
            python_exe = python_home / "python.exe"
            python_site = (Path(sys.prefix) / "Lib" / "site-packages").resolve()
            if not python_exe.is_file():
                raise RuntimeError("sandbox_python_runtime_unavailable")
            if not python_site.is_dir():
                python_site = (python_home / "Lib" / "site-packages").resolve()

            node_home = None
            if command_id.startswith("npm_"):
                node_executable = shutil.which("node")
                node_home = Path(node_executable).resolve().parent if node_executable else None
                npm_cli = node_home / "node_modules" / "npm" / "bin" / "npm-cli.js" if node_home else None
                if node_home is None or npm_cli is None or not npm_cli.is_file():
                    raise RuntimeError("sandbox_node_runtime_unavailable")

            nonce = uuid.uuid4().hex
            request = {
                "command_id": command_id,
                "nonce": nonce,
                "timeout_seconds": timeout,
            }
            (control / "request.json").write_text(json.dumps(request), encoding="utf-8")
            (control / "run.ps1").write_text(self._guest_script(), encoding="utf-8")
            config_path = root / "run.wsb"
            self._write_wsb(
                config_path, control, staged_project, output,
                python_home, python_site, node_home, self.memory_mb,
            )

            # ShellExecute via the .wsb file association is the supported
            # interactive launch path. Starting WindowsSandbox.exe with redirected
            # stdout/stderr can create a remote-session process without booting
            # the disposable VM on this Windows build.
            os.startfile(str(config_path))

            result_path = output / "result.json"
            vm_start_deadline = time.monotonic() + self.STARTUP_GRACE_SECONDS
            result_deadline = vm_start_deadline + timeout + 30
            result = None
            while time.monotonic() < result_deadline:
                vm_started = self._vmmem_pids() - vm_before
                session_started = self._session_pids() - session_before
                if result_path.exists():
                    result = self._safe_result(result_path, nonce)
                    break
                if not vm_started and time.monotonic() >= vm_start_deadline:
                    self._stop_processes(session_started)
                    raise RuntimeError("windows_sandbox_vm_start_timeout")
                time.sleep(1)
            if result is None:
                self._stop_processes(self._vmmem_pids() - vm_before)
                self._stop_processes(self._session_pids() - session_before)
                raise RuntimeError("windows_sandbox_result_timeout")

            shutdown_deadline = time.monotonic() + self.SHUTDOWN_GRACE_SECONDS
            while time.monotonic() < shutdown_deadline:
                remaining = self._vmmem_pids() - vm_before
                if not remaining:
                    break
                time.sleep(1)
            remaining = self._vmmem_pids() - vm_before
            if remaining:
                self._stop_processes(remaining)
                raise RuntimeError("windows_sandbox_shutdown_unconfirmed")
            self._stop_processes(self._session_pids() - session_before)

            stdout = result["stdout"][-self.MAX_OUTPUT_CHARS:]
            stderr = result["stderr"][-self.MAX_OUTPUT_CHARS:]
            completed = subprocess.CompletedProcess(
                args=command,
                returncode=result["exit_code"],
                stdout=stdout,
                stderr=stderr,
            )
            if result["timed_out"]:
                raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
            if result.get("bootstrap_error") or not result["job_limits_applied"]:
                raise RuntimeError("windows_sandbox_resource_limits_unverified")
            return completed
        finally:
            if root is not None:
                active_vms = self._vmmem_pids() - vm_before
                if active_vms:
                    self._stop_processes(active_vms)
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline and self._vmmem_pids() - vm_before:
                        time.sleep(1)
                    active_vms = self._vmmem_pids() - vm_before
                if not active_vms:
                    self._stop_processes(self._session_pids() - session_before)
                    shutil.rmtree(root, ignore_errors=True)
            if process_lock_handle is not None:
                self._release_process_lock(process_lock_handle)
            self._run_lock.release()
