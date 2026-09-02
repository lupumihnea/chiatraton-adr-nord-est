from dataclasses import dataclass
from typing import Optional,List
from datetime import datetime

from Objects import reference


@dataclass
class Obligation:
    id:str
    description:str
    references:List[reference.Reference]
    deadline: Optional[datetime] = None
