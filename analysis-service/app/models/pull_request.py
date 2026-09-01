from datetime import datetime

from sqlalchemy import String, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint

from app.database.base import Base


class PullRequest(Base):

    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_pr_number",
            name="uq_repository_pr"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False
    )

    github_pr_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    source_branch: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    target_branch: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    base_commit_sha: Mapped[str] = mapped_column(
    String,
    nullable=False
    )


    head_commit_sha: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False
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

    repository = relationship(
        "Repository",
        back_populates="pull_requests"
    )