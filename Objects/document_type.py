from enum import Enum
from logging import CRITICAL
from unittest import case

from Importance import *

class DocType(Enum):
    anex=0
    guide=1
    plan_monitor=2
    graph=3
    plan_achizitii=4
    plan_afaceri=5
    cerere_finantare=6
    other=7

def from_int_to_type(type:int):
    return DocType(type)

#TODO de pus ce nivel de importanta are fiecare tip de document
def from_type_to_importance(type:DocType)-> Importance:
    if type == DocType.anex:
        return Importance.Critical
    if type == DocType.guide:
        return Importance.Critical
    if type == DocType.plan_monitor:
        return Importance.Critical
    if type == DocType.graph:
        return Importance.Critical
    if type == DocType.plan_achizitii:
        return Importance.Critical
    if type == DocType.plan_afaceri:
        return Importance.Critical
    if type == DocType.cerere_finantare:
        return Importance.Critical
    if type == DocType.other:
        return Importance.Low