from tornado.process import Subprocess
from typing import Tuple, Union, Optional
from tornado.gen import multi
import shlex

__all__ = ['call_subprocess']


async def call_subprocess(
        cmd: Union[str, list], stdin_data: Optional[str] = None) \
        -> Tuple[int, Union[str, bytes], Union[str, bytes]]:
    """Call sub process async."""

    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    try:
        sub_process = Subprocess(cmd,
                                 stdin=Subprocess.STREAM,
                                 stdout=Subprocess.STREAM,
                                 stderr=Subprocess.STREAM)
    except OSError as e:
        return e.errno, '', e.strerror

    if stdin_data:
        await sub_process.stdin.write(stdin_data)
        sub_process.stdin.close()

    code, result, error = await multi([
        sub_process.wait_for_exit(raise_error=False),
        sub_process.stdout.read_until_close(),
        sub_process.stderr.read_until_close()
    ])

    result = result.strip()
    error = error.strip()

    return code, result, error
