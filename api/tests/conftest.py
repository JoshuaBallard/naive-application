import os
import tempfile
from pathlib import Path

# Set before app.main is imported: it reads these at module scope.
os.environ.setdefault("DATABASE_PATH", str(Path(tempfile.mkdtemp()) / "test.db"))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("IP_HASH_SALT", "test-salt")
# Deliberately not key-shaped: test_no_secret_shaped_string_in_source scans this file.
os.environ.setdefault("ANTHROPIC_API_KEY", "not-a-real-key-for-tests")
