"""File watcher using watchdog. Long-lived process that emits events on change."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger(__name__)

DEFAULT_GLOBS = ("*.py", "*.md", "*.txt", "*.ipynb")


class _Handler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[dict], None], globs: tuple[str, ...]):
        self.callback = callback
        self.globs = globs

    def on_modified(self, event: FileSystemEvent) -> None:
        self._emit(event, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        self._emit(event, "created")

    def _emit(self, event: FileSystemEvent, action: str) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not any(path.match(g) for g in self.globs):
            return
        self.callback({"type": "file_change", "path": str(path), "action": action, "ts": time.time()})


def watch_dirs(dirs: list[Path], callback: Callable[[dict], None], globs: tuple[str, ...] = DEFAULT_GLOBS) -> Observer:
    observer = Observer()
    handler = _Handler(callback, globs)
    for d in dirs:
        d = d.expanduser()
        if not d.exists():
            log.warning("Watch dir does not exist: %s", d)
            continue
        observer.schedule(handler, str(d), recursive=True)
        log.info("Watching %s", d)
    observer.start()
    return observer
