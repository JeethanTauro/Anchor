from datetime import datetime

from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship
from app.database.base import Base


class Repository(Base):

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    github_repo_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False
    )

    owner: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    default_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    last_indexed_commit: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    pull_requests = relationship(
        "PullRequest",
        back_populates="repository"
    )
    indexing_jobs = relationship(
        "IndexingJob",
        back_populates="repository"
    )