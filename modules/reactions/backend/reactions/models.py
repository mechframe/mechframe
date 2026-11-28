"""reactions' table (`dev plans/contracts/reactions.md` §3).

`reactions_reaction`: one person's one reaction to one thing. It names the
thing by its content type and id, with no foreign key: the row is another
module's (SPEC 10). The unique constraint holds a person to one of each key on
a thing, so two presses at once make one row, and it serves the counts' reads
of a thing's reactions too. A person's rows go with their account.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base, refs

#: A reaction's key: `fire`, `mind_blown`.
KEY = r"^[a-z][a-z0-9_]*$"
MAX_KEY = 32


class Reaction(Base):
    __tablename__ = "reactions_reaction"
    __table_args__ = (
        UniqueConstraint(
            "target_type", "target_id", "user_id", "key", name="uq_reactions_reaction_one_each"
        ),
        CheckConstraint(f"target_type ~ '^{refs.TYPE.pattern}$'", name="target_type_known"),
        CheckConstraint(f"key ~ '{KEY}'", name="key_known"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The thing, as `<module>.<entity>` and its id: no foreign key, it's another module's row.
    target_type: Mapped[str] = mapped_column(String(refs.MAX_TYPE))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(MAX_KEY))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
