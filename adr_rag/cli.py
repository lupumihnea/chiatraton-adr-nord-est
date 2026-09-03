from __future__ import annotations

import argparse
import re
import textwrap
from datetime import datetime

from sqlalchemy import select

from .db import Document, Obligation, Project, SessionLocal, get_documents, get_project, init_db
from .pipeline import run_extraction


def _display_text(text: str, indent: str = "", width: int = 118) -> str:
    """
    Display-only formatting.

    The database keeps the exact original Romanian source substring. Here we
    collapse parser-introduced whitespace/newlines and wrap at a normal console
    width so PDF line breaks do not produce one or two words per line.
    No words, punctuation, spelling, or diacritics are changed.
    """
    clean = re.sub(r"\s+", " ", text or "").strip()
    return textwrap.fill(
        clean,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def cmd_init_db(_args):
    init_db()
    print("Database initialized")


def cmd_add_project(args):
    with SessionLocal() as s:
        project = Project(
            id=args.id,
            call_id=args.call_id,
            time_ending=datetime.fromisoformat(args.time_ending) if args.time_ending else None,
            name=args.name,
        )
        s.add(project)
        s.commit()
        print(f"Added project {project.id}")


def cmd_add_document(args):
    with SessionLocal() as s:
        doc = Document(type=args.type, path=args.path)
        s.add(doc)
        s.commit()
        print(f"Added document {doc.id}: {doc.path}")


def cmd_extract(args):
    with SessionLocal() as s:
        project = get_project(s, args.project_id)
        docs = get_documents(s, args.document_ids)
        saved = run_extraction(s, project, docs)

    # Integrated workflow: remember which documents belong to this project so
    # report analysis can compare against contract/anexes/relevant sources.
    from DataBase.db_schema import setup_database
    from Repositories.project_document_repository import ProjectDocumentRepository
    con = setup_database()
    try:
        ProjectDocumentRepository.link_many(
            con.cursor(), args.project_id, args.document_ids, "project_document"
        )
        con.commit()
    finally:
        con.close()

    print(f"Saved {len(saved)} obligations")
    for o in saved:
            print(f"[{o.importance}] #{o.id} | deadline={o.deadline}")
            print(_display_text(o.description, indent="    "))
            if o.references:
                r = o.references[0]
                print(
                    f"    source: document={r.document_id} page={r.page} "
                    f"chapter={r.chapter!r} subchapter={r.subchapter!r}"
                )


def cmd_list(args):
    with SessionLocal() as s:
        rows = list(
            s.scalars(
                select(Obligation)
                .where(Obligation.project_id == args.project_id)
                .order_by(Obligation.importance.desc(), Obligation.id)
            )
        )
        for o in rows:
            print(f"[{o.importance}] #{o.id}")
            print(_display_text(o.description, indent="    "))
            print(f"    deadline: {o.deadline}")
            for r in o.references:
                print(
                    f"    ref: document={r.document_id} page={r.page} "
                    f"chapter={r.chapter!r} subchapter={r.subchapter!r}"
                )
                print(_display_text(r.text, indent="         "))


def build_parser():
    p = argparse.ArgumentParser(description="Local ADR obligation extraction RAG")
    sub = p.add_subparsers(required=True)

    x = sub.add_parser("init-db")
    x.set_defaults(fn=cmd_init_db)

    x = sub.add_parser("add-project")
    x.add_argument("--id", type=int, required=True, help="6-digit project code")
    x.add_argument("--call-id", type=int)
    x.add_argument("--time-ending", help="ISO timestamp/date")
    x.add_argument("--name")
    x.set_defaults(fn=cmd_add_project)

    x = sub.add_parser("add-document")
    x.add_argument("--type", type=int, required=True)
    x.add_argument("--path", required=True)
    x.set_defaults(fn=cmd_add_document)

    x = sub.add_parser("extract")
    x.add_argument("--project-id", type=int, required=True)
    x.add_argument("--document-ids", type=int, nargs="+", required=True)
    x.set_defaults(fn=cmd_extract)

    x = sub.add_parser("list")
    x.add_argument("--project-id", type=int, required=True)
    x.set_defaults(fn=cmd_list)

    return p


def main():
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
