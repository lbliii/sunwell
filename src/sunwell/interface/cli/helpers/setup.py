"""Environment setup utilities."""

import os
from pathlib import Path


def load_dotenv() -> None:
    """Load .env file if it exists and is readable."""
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        # Remove quotes if present
                        value = value.strip().strip("'\"")
                        os.environ.setdefault(key.strip(), value)
        except PermissionError:
            # Can't read .env (sandboxed environment, etc.) - continue without it
            pass
        except OSError:
            # Other file access issues - continue without it
            pass
