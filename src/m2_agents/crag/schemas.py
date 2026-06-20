from enum import StrEnum

from pydantic import BaseModel


class GradeEnum(StrEnum):
    RELEVANT = "RELEVANT"
    AMBIGUOUS = "AMBIGUOUS"
    IRRELEVANT = "IRRELEVANT"


class CRAGGrade(BaseModel):
    chunk_id: str
    grade: GradeEnum
    reason: str
