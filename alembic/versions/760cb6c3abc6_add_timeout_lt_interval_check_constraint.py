"""add timeout_lt_interval check constraint

Revision ID: 760cb6c3abc6
Revises: ce2eaa1d5158
Create Date: 2026-07-21 20:28:46.246836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '760cb6c3abc6'
down_revision: Union[str, Sequence[str], None] = 'ce2eaa1d5158'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_check_constraint(
        "ck_endpoint_target_timeout_lt_interval",
        "endpoint_target",
        "timeout_seconds < interval_seconds"
    )

def downgrade():
    op.drop_constraint(
        "ck_endpoint_target_timeout_lt_interval",
        "endpoint_target",
        type_="check"
    )
