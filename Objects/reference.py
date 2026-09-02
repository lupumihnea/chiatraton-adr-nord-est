from dataclasses import dataclass
from typing import Optional

@dataclass
class Reference:
    reference_id: str
    document_link:str
    page:Optional[str]
    text:Optional[str]
    chapter:Optional[str]
    subject:Optional[str]