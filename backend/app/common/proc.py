import subprocess

from returns.io import IOFailure, IOResult, IOSuccess


def run_subprocess(
    cmd: list[str],
) -> IOResult[subprocess.CompletedProcess, subprocess.CalledProcessError]:
    proc = subprocess.run(cmd, capture_output=True)
    try:
        proc.check_returncode()
        return IOSuccess.from_value(proc)
    except subprocess.CalledProcessError as e:
        return IOFailure.from_failure(e)
