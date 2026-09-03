from dataclasses import dataclass
from typing import Optional,List
from datetime import datetime

from DAO.obligations_DAO import ObligationDAO
from Objects.reference import Reference


@dataclass
class Obligation:
    id:str
    description:str
    references:List[Reference]
    deadline: Optional[datetime] = None

    @staticmethod
    def from_DAO(dao: ObligationDAO, references:List[Reference]) -> Obligation:
        return Obligation(
            references=references,
            id=dao.id,
            description=dao.description  if dao.description else "there is no description available",
            deadline=dao.deadline
        )
