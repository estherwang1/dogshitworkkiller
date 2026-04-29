"""子进程代理
用 subprocess.Popen 启动任务脚本,实时读 stdout 并通过回调推送给调用方。

设计要点:
- 用线程读 stdout,避免阻塞 Tkinter 主线程
- 回调函数在子线程里执行,调用方负责线程安全(Tkinter 的 after 机制)
- 支持查询运行状态和等待结束
"""

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional


class RunnerProxy:
    """管理一个子进程的生命周期。

    典型用法:
        proxy = RunnerProxy()
        proxy.start(script_path, task_dir, on_line=..., on_finish=...)
        # ... 等 on_finish 回调被调用
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(
        self,
        script_path: Path,
        task_dir: Path,
        *,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        """启动子进程。

        Args:
            script_path: 要运行的 Python 脚本的绝对路径。
            task_dir: 任务目录,作为命令行参数传给脚本。
            on_line: 每读到一行 stdout/stderr 时调用,参数是该行文本(含换行)。
            on_finish: 子进程结束时调用,参数是 returncode。

        Raises:
            RuntimeError: 已有进程在运行。
        """
        if self._running:
            raise RuntimeError("已有任务在运行")

        self._running = True

        # 构建子进程环境,确保 PYTHONUTF8=1 传递下去
        env = os.environ.copy()

        self._process = subprocess.Popen(
            [sys.executable, str(script_path), str(task_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        def _reader():
            try:
                for line in self._process.stdout:
                    on_line(line)
            except Exception:
                pass
            finally:
                self._process.wait()
                self._running = False
                on_finish(self._process.returncode)

        self._thread = threading.Thread(target=_reader, daemon=True)
        self._thread.start()
