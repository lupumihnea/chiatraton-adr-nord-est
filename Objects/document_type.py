from enum import IntEnum

from Objects.Importance import Importance


class DocType(IntEnum):
    financing_application = 1
    business_plan = 2
    business_plan_annex = 3
    monitoring_plan = 4
    procurement_plan = 5
    payment_schedule = 6
    progress_report = 7
    beneficiary_manual = 8
    funding_guide = 9
    contract = 10
    addendum = 11
    declaration = 12
    other = 99

    # Legacy aliases retained for old UI/code.
    cerere_finantare = 1
    plan_afaceri = 2
    anex = 3
    plan_monitor = 4
    plan_achizitii = 5
    graph = 6
    guide = 9


def from_int_to_type(type_: int) -> DocType:
    return DocType(type_)


def from_type_to_importance(type_: DocType) -> Importance:
    return Importance.Low if type_ == DocType.other else Importance.Critical
