"""
Query rewriter for CRAG Tier-1 fallback.

When initial retrieval scores below the CRAG threshold, the rewriter
produces a semantically richer query to improve recall on retry.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.prompts.rewrite import REWRITE_SYSTEM_PROMPT, build_rewrite_user_prompt
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """
    Rewrites queries for improved retrieval recall.

    Uses an LLM to expand entities, add temporal context, and
    rephrase for semantic search compatibility.
    """

    def __init__(self, llm=None) -> None:  # noqa: ANN001
        self._llm = llm

    async def _get_llm(self):  # noqa: ANN202
        if self._llm is None:
            self._llm = get_chat_model_with_fallback(temperature=0.3)
        return self._llm

    async def rewrite(self, original_query: str) -> str:
        """
        Produce a semantically enhanced version of the query.

        Args:
            original_query: The user's raw query that scored poorly.

        Returns:
            A rewritten query string optimised for vector retrieval.
            Returns the original query unchanged if rewriting fails.
        """
        llm = await self._get_llm()

        try:
            messages = [
                SystemMessage(content=REWRITE_SYSTEM_PROMPT),
                HumanMessage(content=build_rewrite_user_prompt(original_query)),
            ]
            response = await llm.ainvoke(messages)
            rewritten = response.content.strip()

            if not rewritten or len(rewritten) < 5:
                logger.warning("Rewriter returned empty result, using original")
                return original_query

            logger.info(
                "Query rewritten",
                original=original_query,
                rewritten=rewritten,
            )
            return rewritten

        except Exception as exc:  # noqa: BLE001
            logger.warning("Query rewrite failed", error=str(exc))
            return original_query
