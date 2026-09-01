from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class IndexingJob(Base):

    __tablename__ = "indexing_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False
    )

    commit_sha: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    trigger_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="QUEUED"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    files_processed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    chunks_created: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    repository = relationship(
        "Repository",
        back_populates="indexing_jobs"
    )