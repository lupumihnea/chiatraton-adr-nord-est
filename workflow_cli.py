from __future__ import annotations

import argparse
import json

from API.monitoring_api import MonitoringAPI
from DataBase.db_schema import database_path, setup_database


api = MonitoringAPI()


def init_db(_args):
    con = setup_database()
    con.close()
    print(f"Database ready: {database_path()}")


def list_projects(_args):
    for p in api.list_projects():
        print(f"{p['id']} | {p.get('name')} | end={p.get('time_ending')}")


def link_documents(args):
    api.link_documents(args.project_id, args.document_ids, args.role)
    print(f"Linked {len(args.document_ids)} documents to project {args.project_id}")


def extract_criteria(args):
    rows = api.extract_criteria(args.project_id, args.document_ids)
    print(f"Saved {len(rows)} criteria")
    for row in rows:
        print(f"[{row['importance']}] #{row['id']} {row['description']}")


def add_report(args):
    report_id = api.add_report(
        project_id=args.project_id,
        document_id=args.document_id,
        sequence_number=args.sequence,
        kind=args.kind,
        period_start=args.period_start,
        period_end=args.period_end,
    )
    print(f"Added report {report_id}")


def list_reports(args):
    for r in api.list_reports(args.project_id):
        print(
            f"#{r['id']} seq={r['sequence_number']} kind={r['kind']} "
            f"period={r['period_start']}..{r['period_end']} status={r['status']}"
        )


def analyze(args):
    findings = api.analyze_report(args.report_id, force=args.force)
    print(f"Displayed exceptions: {len(findings)}")
    for f in findings:
        print(f"[{f['outcome']}] validation={f['id']} criterion={f['criterion_id']}")
        print(f"  {f['rationale']}")
        for s in f.get('sources', [])[:2]:
            print(f"  source {s['role']}: document={s['document_id']} page={s['page']}")
            print(f"    {' '.join((s['text'] or '').split())}")


def findings(args):
    rows = api.list_findings(args.report_id)
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


def decide(args):
    decision_id = api.decide(
        args.validation_id,
        args.action,
        final_outcome=args.final_outcome,
        corrected_text=args.corrected_text,
        comment=args.comment,
        decided_by=args.decided_by,
    )
    print(f"Saved decision {decision_id}")


def generate(args):
    out = api.generate_output(args.report_id, args.kind)
    print(out['path'])
    print(out['content'])


def history(args):
    print(json.dumps(api.history(args.report_id), ensure_ascii=False, indent=2, default=str))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ADR report-monitoring workflow")
    sub = p.add_subparsers(required=True)

    x = sub.add_parser("init-db")
    x.set_defaults(fn=init_db)

    x = sub.add_parser("list-projects")
    x.set_defaults(fn=list_projects)

    x = sub.add_parser("link-documents")
    x.add_argument("--project-id", type=int, required=True)
    x.add_argument("--document-ids", type=int, nargs="+", required=True)
    x.add_argument("--role", default="project_document")
    x.set_defaults(fn=link_documents)

    x = sub.add_parser("extract-criteria")
    x.add_argument("--project-id", type=int, required=True)
    x.add_argument("--document-ids", type=int, nargs="+", required=True)
    x.set_defaults(fn=extract_criteria)

    x = sub.add_parser("add-report")
    x.add_argument("--project-id", type=int, required=True)
    x.add_argument("--document-id", type=int, required=True)
    x.add_argument("--sequence", type=int, required=True)
    x.add_argument(
        "--kind",
        choices=["implementation_progress", "final_progress", "durability"],
        default="implementation_progress",
    )
    x.add_argument("--period-start", required=True)
    x.add_argument("--period-end", required=True)
    x.set_defaults(fn=add_report)

    x = sub.add_parser("list-reports")
    x.add_argument("--project-id", type=int, required=True)
    x.set_defaults(fn=list_reports)

    x = sub.add_parser("analyze-report")
    x.add_argument("--report-id", type=int, required=True)
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=analyze)

    x = sub.add_parser("findings")
    x.add_argument("--report-id", type=int, required=True)
    x.set_defaults(fn=findings)

    x = sub.add_parser("decide")
    x.add_argument("--validation-id", type=int, required=True)
    x.add_argument(
        "--action",
        choices=["confirmed", "corrected", "rejected", "clarification_requested"],
        required=True,
    )
    x.add_argument("--final-outcome")
    x.add_argument("--corrected-text")
    x.add_argument("--comment")
    x.add_argument("--decided-by", default="utilizator")
    x.set_defaults(fn=decide)

    x = sub.add_parser("generate")
    x.add_argument("--report-id", type=int, required=True)
    x.add_argument("--kind", choices=["verification_note", "clarification_draft"], required=True)
    x.set_defaults(fn=generate)

    x = sub.add_parser("history")
    x.add_argument("--report-id", type=int, required=True)
    x.set_defaults(fn=history)

    return p


if __name__ == "__main__":
    args = parser().parse_args()
    args.fn(args)
