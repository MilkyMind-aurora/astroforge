"""0001 基线：创建方案 3.9 全部 10 张表

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-31

说明：基线迁移直接以 ORM 元数据建表（create_all）；
后续迁移一律 alembic revision --autogenerate 生成增量脚本。
"""
from typing import Sequence, Union

from alembic import op

from astroforge.db import models

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    models.Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    models.Base.metadata.drop_all(bind=op.get_bind())
