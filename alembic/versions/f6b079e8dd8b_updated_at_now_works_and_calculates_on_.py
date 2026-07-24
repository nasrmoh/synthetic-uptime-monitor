"""updated_at now works and calculates on server side

Revision ID: f6b079e8dd8b
Revises: 634f0634534d
Create Date: 2026-07-24 22:58:28.270554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b079e8dd8b'
down_revision: Union[str, Sequence[str], None] = '634f0634534d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No DDL change. EndpointTarget.updated_at gained onupdate=func.now(),
    # which is enforced by SQLAlchemy at UPDATE-time (it attaches the
    # literal SQL expression now() to the UPDATE statement). This has
    # no representation in Postgres's column definition or catalog,
    # so there is nothing for Alembic to alter. This revision exists
    # only to mark the point in migration history where that model
    # behavior changed.
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # No DDL change to reverse; see upgrade().
    pass
