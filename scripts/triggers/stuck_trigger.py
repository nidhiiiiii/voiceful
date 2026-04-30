"""Stuck trigger. Fires on repeated errors / repeated test runs."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

ERROR_RE = re.compile(r"(?i)(error|exception|traceback|failed|failure|fatal)")
TEST_RE = re.compile(r"(?i)\b(pytest|npm test|yarn test|go test|cargo test|jest)\b")


def detect(events: list[dict[str, Any]], state: dict[str, Any] | None = None, threshold: int = 3) -> list[dict[str, Any]]:
    if state is None:
        state = {}
    out: list[dict[str, Any]] = []
    seen_signatures = set(state.get("stuck_seen", []))

    error_lines = [ev.get("line", "") for ev in events if ev.get("type") == "shell_command" and ERROR_RE.search(ev.get("line", ""))]
    if error_lines:
        counts = Counter(error_lines)
        for line, cnt in counts.items():
            sig = f"err:{line[:80]}"
            if cnt >= threshold and sig not in seen_signatures:
                out.append({
                    "type": "stuck",
                    "context": f"hit this {cnt} times: {line[:120]}",
                    "raw_signal": {"error_line": line, "count": cnt},
                })
                seen_signatures.add(sig)

    test_lines = [ev.get("line", "") for ev in events if ev.get("type") == "shell_command" and TEST_RE.search(ev.get("line", ""))]
    if len(test_lines) >= threshold:
        sig = f"tests:{test_lines[0][:60]}"
        if sig not in seen_signatures:
            out.append({
                "type": "stuck",
                "context": f"running tests repeatedly ({len(test_lines)} times)",
                "raw_signal": {"recent_test_runs": test_lines[-5:]},
            })
            seen_signatures.add(sig)

    state["stuck_seen"] = list(seen_signatures)[-100:]
    return out
