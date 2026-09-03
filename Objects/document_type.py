from enum import Enum
from logging import CRITICAL
from unittest import case


class DocType(Enum):
    general_documents=0
    initial_project_documents=1
    progress_report=2
    other_documents=3

def from_int_to_type(type:int):
    return DocType(type)