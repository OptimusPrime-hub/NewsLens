"""
CRAG chunk evaluator — grades retrieved chunks for relevance.

BaseCRAGEvaluator defines the interface; LLMCRAGEvaluator is the
default implementation. Future alternatives (RuleBasedCRAG, HybridCRAG)
can be swapped in without touching graph code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.crag.schemas import CRAGGrade, GradeEnum
from src.m2_agents.prompts.crag import CRAG_SYSTEM_PROMPT, build_crag_user_prompt
from src.m2_agents.schemas import RetrievedChunk
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BaseCRAGEvaluator(ABC):
    """
    Protocol for CRAG evaluators.

    Implementations grade each chunk as RELEVANT / AMBIGUOUS / IRRELEVANT
    relative to the user query.
    """

    @abstractmethod
    async def evaluate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> list[CRAGGrade]:
        """
        Grade each chunk for relevance to the query.

        Args:
            query: The user's original query.
            chunks: Retrieved document chunks to evaluate.

        Returns:
            A CRAGGrade per chunk with grade + reason.
        """


class LLMCRAGEvaluator(BaseCRAGEvaluator):
    """
    LLM-based CRAG evaluator.

    Sends each chunk to the LLM for a RELEVANT/AMBIGUOUS/IRRELEVANT
    classification with a brief justification.
    """

    def __init__(self, llm=None) -> None:  # noqa: ANN001
        self._llm = llm

    async def _get_llm(self):  # noqa: ANN202
        if self._llm is None:
            self._llm = get_chat_model_with_fallback(temperature=0.0, purpose="m1")
        return self._llm

    async def evaluate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> list[CRAGGrade]:
        """
        Grade each chunk using LLM classification.

        Processes chunks in a single batch prompt for efficiency.
        Falls back to AMBIGUOUS if LLM output can't be parsed.
        """
        if not chunks:
            return []

        try:
            llm = await self._get_llm()
            grades: list[CRAGGrade] = []

            for chunk in chunks:
                grade = await self._grade_single(llm, query, chunk)
                grades.append(grade)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CRAG evaluation failed completely, defaulting all chunks to AMBIGUOUS",
                error=str(exc)
            )
            return [
                CRAGGrade(
                    chunk_id=chunk.chunk_id,
                    grade=GradeEnum.AMBIGUOUS,
                    reason=f"LLM evaluation failed or offline: {exc}",
                )
                for chunk in chunks
            ]

        relevant = sum(1 for g in grades if g.grade == GradeEnum.RELEVANT)
        logger.info(
            "CRAG evaluation complete",
            total=len(grades),
            relevant=relevant,
            ambiguous=sum(1 for g in grades if g.grade == GradeEnum.AMBIGUOUS),
            irrelevant=sum(1 for g in grades if g.grade == GradeEnum.IRRELEVANT),
        )

        return grades

    async def _grade_single(
        self,
        llm,  # noqa: ANN001
        query: str,
        chunk: RetrievedChunk,
    ) -> CRAGGrade:
        """Grade a single chunk, with safe fallback on parse failure."""
        try:
            messages = [
                SystemMessage(content=CRAG_SYSTEM_PROMPT),
                HumanMessage(content=build_crag_user_prompt(query, chunk)),
            ]
            response = await llm.ainvoke(messages)
            return self._parse_grade(chunk.chunk_id, response.content)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "CRAG grade failed, defaulting to AMBIGUOUS",
                chunk_id=chunk.chunk_id,
                error=str(exc),
            )
            return CRAGGrade(
                chunk_id=chunk.chunk_id,
                grade=GradeEnum.AMBIGUOUS,
                reason=f"Evaluation failed: {exc}",
            )

    @staticmethod
    def _parse_grade(chunk_id: str, raw: str) -> CRAGGrade:
        """
        Parse LLM text output into a CRAGGrade.

        Expected format: 'GRADE: RELEVANT\\nREASON: ...'
        Falls back to AMBIGUOUS if parsing fails.
        """
        raw_upper = raw.strip().upper()

        # Determine grade
        if "RELEVANT" in raw_upper and "IRRELEVANT" not in raw_upper:
            grade = GradeEnum.RELEVANT
        elif "IRRELEVANT" in raw_upper:
            grade = GradeEnum.IRRELEVANT
        else:
            grade = GradeEnum.AMBIGUOUS

        # Extract reason (everything after first newline, or full text)
        lines = raw.strip().split("\n", 1)
        reason = lines[1].strip() if len(lines) > 1 else raw.strip()
        # Strip common prefixes
        for prefix in ("REASON:", "Reason:", "reason:"):
            if reason.startswith(prefix):
                reason = reason[len(prefix):].strip()
                break

        return CRAGGrade(chunk_id=chunk_id, grade=grade, reason=reason)
