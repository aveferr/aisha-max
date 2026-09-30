"""move demo city from Kazan to Saint Petersburg

Площадки, события и пользователи уже созданной базы привязаны к городу по id, поэтому
город переименовывается, а не создаётся заново: иначе у существующих пользователей
афиша осталась бы пустой. На чистой базе миграция ничего не делает.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 23:40:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE cities SET name = 'Санкт-Петербург' WHERE name = 'Казань' "
        "AND NOT EXISTS (SELECT 1 FROM cities WHERE name = 'Санкт-Петербург')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE cities SET name = 'Казань' WHERE name = 'Санкт-Петербург' "
        "AND NOT EXISTS (SELECT 1 FROM cities WHERE name = 'Казань')"
    )
