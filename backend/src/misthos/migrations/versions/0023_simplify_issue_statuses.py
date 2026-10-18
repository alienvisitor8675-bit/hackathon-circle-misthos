"""Move issues off the two statuses the lifecycle no longer has.

`REWORK` and `ACCEPTED` were the same positions in the flow seen twice: a failed
review leaves the contributor holding the issue, and a passing review is still a
pull request waiting to be merged. The statuses are gone from the domain, so every
stored row moves to the one that remains. The verdict stays on the review record,
which is what tells the issue page whether the work needs changes or is ready to
merge.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-18
"""

from __future__ import annotations

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE issues SET state = 'CLAIMED' WHERE state = 'REWORK'")
    op.execute("UPDATE issues SET state = 'IN_REVIEW' WHERE state = 'ACCEPTED'")


def downgrade() -> None:
    """Best effort: the state alone no longer says which of the two an issue came
    from, so the review verdict decides where a row can go back. A claimed issue
    without a failed verdict stays claimed, which the old lifecycle also allowed."""
    op.execute(
        """
        UPDATE issues
        SET state = 'REWORK'
        WHERE state = 'CLAIMED'
          AND EXISTS (
              SELECT 1 FROM reviews
              WHERE reviews.issue_id = issues.id AND reviews.verdict = 'rework'
          )
        """
    )
    op.execute(
        """
        UPDATE issues
        SET state = 'ACCEPTED'
        WHERE state = 'IN_REVIEW'
          AND accepted_by IS NULL
          AND EXISTS (
              SELECT 1 FROM reviews
              WHERE reviews.issue_id = issues.id AND reviews.verdict = 'accept'
          )
        """
    )
