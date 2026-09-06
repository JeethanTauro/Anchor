from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IndexingJob(Base):

    __tablename__ = "indexing_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    repository_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    commit_sha: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
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
        nullable=False
    )

    chunks_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )