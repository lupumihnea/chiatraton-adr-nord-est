from __future__ import annotations

import runpy
import sys

from dotenv import load_dotenv

load_dotenv()

RAG_COMMANDS = {"init-db", "add-project", "add-document", "extract", "list"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in RAG_COMMANDS:
        from adr_rag.cli import main as rag_main

        rag_main()
    else:
        runpy.run_module("Interface.main", run_name="__main__")
