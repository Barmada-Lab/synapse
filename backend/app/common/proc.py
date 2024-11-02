import asyncio
import subprocess


async def run_subproc_async(cmd, check=True):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()

    # Check the return code
    return_code = proc.returncode
    if check and return_code != 0:
        raise subprocess.CalledProcessError(
            return_code, cmd, output=stdout, stderr=stderr
        )

    return return_code, stdout, stderr
