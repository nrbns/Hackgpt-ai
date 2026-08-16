"""Baseline revision — stamps Alembic; schema bootstrap remains init_schema().

Forward-looking DDL changes belong in new revisions after this baseline.
For cloud: run `alembic upgrade head` then start the app (init_schema is idempotent).
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Marker table so operators can confirm migrations ran.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS securaiq_schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        """
        INSERT INTO securaiq_schema_meta (key, value, updated_at)
        VALUES ('alembic_baseline', '0001_baseline', EXTRACT(EPOCH FROM NOW()))
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM securaiq_schema_meta WHERE key = 'alembic_baseline'")
