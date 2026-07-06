"""PromoAgent — AI Promotion Agent for Launches, Ads, and Multi-Platform Copy."""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env from cwd or any parent directory, skipping keys already set."""
    for directory in [Path.cwd(), *Path.cwd().parents]:
        env_file = directory / ".env"
        if env_file.is_file():
            try:
                for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
            except OSError:
                pass
            break


_load_dotenv()

from .analyzer import analyze_target  # noqa: E402
from .ai import generate_ai_content  # noqa: E402
from .optimize import run_optimize  # noqa: E402

__version__ = "0.3.0"

__all__ = [
    "__version__",
    "analyze_target",
    "generate_ai_content",
    "run_optimize",
]
