from enum import Enum

class Importance(Enum):
    Low = 0
    Important=1
    Critical=2

def from_int_to_importance(importance: int) -> Importance:
    return Importance(importance)