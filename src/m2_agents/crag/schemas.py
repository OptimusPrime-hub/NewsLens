from enum import Enum
from pydantic import BaseModel

class GradeEnum(str, Enum):
    RELEVANT = "RELEVANT"
    AMBIGUOUS = "AMBIGUOUS"
    IRRELEVANT = "IRRELEVANT"

class CRAGGrade(BaseModel):
    chunk_id: str
    grade: GradeEnum
    reason: str
