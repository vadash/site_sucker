"""Unified progress tracking for pipeline stages.

Provides a reusable progress counter that prints on a single line,
giving all pipeline stages a consistent look:

    [4/4] Stripping online-only resources for offline browsing... (4514 file(s))
      [2273/4514]
"""


class ProgressTracker:
    """Single-line progress counter for pipeline stages.

    Prints ``  [current/total]`` on the same line using carriage return,
    finishing with a newline when done.
    """

    def __init__(self, total: int) -> None:
        self.total = total
        self._current = 0

    def update(self, current: int) -> None:
        """Overwrite the progress line with the given counter value."""
        self._current = current
        print(f"\r  [{current}/{self.total}]", end="", flush=True)

    def tick(self) -> None:
        """Advance the counter by one and refresh the line."""
        self._current += 1
        self.update(self._current)

    def finish(self) -> None:
        """Print a trailing newline so subsequent output starts on a fresh line."""
        if self.total > 0:
            print(flush=True)
