import subprocess
import sys

from conftest import BACKEND_DIR


def test_models_match_migrations():
    """Модели и миграции не должны расходиться: иначе `alembic check` найдёт разницу."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
