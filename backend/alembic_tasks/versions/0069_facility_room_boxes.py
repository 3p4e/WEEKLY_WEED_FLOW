"""room geometry on the facility register: the rectangle each room occupies

Revision ID: 0069
Revises: 0068
Create Date: 2026-09-06

0068 gave every room an anchor point, which is enough to drop a pin on a picture
of the architect's sheet. It is not enough for the app to DRAW the building
itself, and a scan of a white CAD sheet is the one surface in this app that
cannot be themed, cannot be read on a phone, and cannot colour a room by what
is happening in it.

So each room now carries a rectangle as well. Where it comes from matters,
because the app must not imply a survey it did not do:

  - The SIZE is exact. Every room is stamped with its area and its perimeter,
    and for a rectangle those two give the sides outright: w + h = P/2 and
    w·h = A. 187 of the 191 rooms solve to a real pair; the rest fall back to a
    square of the right area.
  - The POSITION and the ORIENTATION are FITTED. A rectangle of the known size
    is slid around the room's own code stamp, in both orientations, and scored
    against the drawing's wall ink: a correctly placed room has almost no wall
    inside it and a lot of wall along its edge. The same sweep recovered the
    sheet's true scale (14.2 pt per metre, not the 1:100 the title block prints
    — the drawing was exported at about half scale).
  - `box_conf` is that edge score, 0..1. It is stored rather than thrown away
    because it is the honest part: a wardrobe packed with locker runs or a
    2 m fire-escape sliver scores low, and the app draws those rooms as
    approximate instead of pretending they are surveyed.

Nothing downstream depends on the geometry, so every column is nullable and a
room with no stamped area simply has no box.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in ("box_x", "box_y", "box_w", "box_h", "box_conf"):
        op.execute(f"ALTER TABLE public.facility_rooms ADD COLUMN {col} numeric")
    # The box lives in the same normalised frame as plan_x / plan_y, so a pin
    # and its room are drawn in one coordinate space with no arithmetic in the
    # view. All five columns travel together or none of them do.
    op.execute(
        "ALTER TABLE public.facility_rooms ADD CONSTRAINT facility_rooms_box_check CHECK ("
        " ((box_x IS NULL) = (box_y IS NULL))"
        " AND ((box_x IS NULL) = (box_w IS NULL))"
        " AND ((box_x IS NULL) = (box_h IS NULL))"
        " AND ((box_x IS NULL) OR ("
        "   (box_x >= (0)::numeric) AND (box_y >= (0)::numeric)"
        "   AND (box_w > (0)::numeric) AND (box_h > (0)::numeric)"
        "   AND ((box_x + box_w) <= (1)::numeric)"
        "   AND ((box_y + box_h) <= (1)::numeric)))"
        " AND ((box_conf IS NULL) OR ((box_conf >= (0)::numeric)"
        "   AND (box_conf <= (1)::numeric))))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.facility_rooms DROP CONSTRAINT facility_rooms_box_check")
    for col in ("box_conf", "box_h", "box_w", "box_y", "box_x"):
        op.execute(f"ALTER TABLE public.facility_rooms DROP COLUMN {col}")
