from enum import Enum
from logging import CRITICAL
from unittest import case


class DocType(Enum):
    initial_document=0
    progress_report=1

def from_int_to_type(type:int):
    return DocType(type)