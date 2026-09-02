from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import DateTime, ForeignKey, Integer, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "project"

    # The caller is expected to provide the 6-digit project code.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    call_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_ending: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)

    obligations: Mapped[list["Obligation"]] = relationship(back_populates="project")


class Obligation(Base):
    __tablename__ = "obligation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="obligations")
    references: Mapped[list["Reference"]] = relationship(
        back_populates="obligation", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)

    references: Mapped[list["Reference"]] = relationship(back_populates="document")


class Reference(Base):
    __tablename__ = "references"

    # Your DBML already contains an id column. We use it as the technical PK.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obligation_id: Mapped[int] = mapped_column(
        ForeignKey("obligation.id"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id"), nullable=False, index=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chapter: Mapped[str | None] = mapped_column(Text, nullable=True)
    subchapter: Mapped[str | None] = mapped_column(Text, nullable=True)

    obligation: Mapped[Obligation] = relationship(back_populates="references")
    document: Mapped[Document] = relationship(back_populates="references")


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} does not exist")
    return project


def get_documents(session: Session, document_ids: Iterable[int]) -> list[Document]:
    ids = list(document_ids)
    if not ids:
        return []
    docs = list(session.scalars(select(Document).where(Document.id.in_(ids))))
    found = {d.id for d in docs}
    missing = sorted(set(ids) - found)
    if missing:
        raise ValueError(f"Unknown document ids: {missing}")
    return docs
