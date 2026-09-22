"""Guard the one thing Alembic does not guard by itself.

Alembic keeps the database in step with the *migrations*. Nothing keeps
the migrations in step with the *models*: you can edit db_schema.py,
forget `alembic revision --autogenerate`, and everything passes — locally,
because your dev database was built by an older create_all; in CI,
because the tests build their schema straight from the models. The
divergence then surfaces in production, as the one place where the
schema is real and nobody ran the missing migration.

So: build a database from the migrations alone, and ask Alembic whether
any upgrade operation would still be needed. That is exactly what
`alembic check` does, run here against a throwaway SQLite file.

This is the same class of test as test_taxonomy.py — a regression that is
invisible at runtime until it is expensive.
"""

import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent


def _alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )


def test_migrations_match_the_models(tmp_path):
    """A database built only from the migrations must match db_schema.

    If this fails, the models were changed without a migration. Fix it with:
        .venv/bin/python -m alembic revision --autogenerate -m "what changed"
    and read the generated file — autogenerate renders a rename as a DROP
    plus an ADD, which loses the column's data.
    """
    url = f"sqlite:///{tmp_path / 'schema_check.db'}"

    built = _alembic("upgrade", "head", database_url=url)
    assert built.returncode == 0, f"`alembic upgrade head` failed:\n{built.stderr}"

    check = _alembic("check", database_url=url)
    assert check.returncode == 0, (
        "The models and the migrations have diverged — a migration is missing.\n"
        f"{check.stdout}\n{check.stderr}"
    )


def test_migrations_are_reversible(tmp_path):
    """Every migration has a downgrade that runs.

    Not because downgrades get used in production — they rarely should —
    but because writing one forces the author to say what the change
    actually did, and a downgrade that raises is usually a migration that
    wasn't thought through.
    """
    url = f"sqlite:///{tmp_path / 'downgrade_check.db'}"

    up = _alembic("upgrade", "head", database_url=url)
    assert up.returncode == 0, f"`alembic upgrade head` failed:\n{up.stderr}"

    down = _alembic("downgrade", "base", database_url=url)
    assert down.returncode == 0, f"`alembic downgrade base` failed:\n{down.stderr}"


def test_single_migration_head():
    """One head, so `upgrade head` is never ambiguous.

    Two heads mean two branches of history — usually two people generating
    a revision from the same parent — and Alembic refuses to upgrade until
    they are merged. Catching it here is cheaper than catching it on deploy.
    """
    heads = _alembic("heads", database_url="sqlite:///:memory:")
    assert heads.returncode == 0, heads.stderr
    lines = [ln for ln in heads.stdout.splitlines() if ln.strip() and not ln.startswith("INFO")]
    assert len(lines) == 1, f"expected exactly one migration head, got:\n{heads.stdout}"
