"""
Framing extraction module.
Uses LLM structured output to classify text into a 5-dimension FramingVector.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.m3_bias.schemas import FramingVector
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger
from src.shared.prompts.framing import FRAMING_SYSTEM_PROMPT, build_framing_user_prompt

logger = get_logger(__name__)


class FramingExtractor:
    """
    Extracts a 5-dimensional narrative framing vector from publisher articles.
    """

    async def extract(self, publisher: str, topic: str, chunks_text: str) -> FramingVector:
        """
        Extract framing vector using LLM with structured output.
        """
        if not chunks_text.strip():
            return FramingVector(
                conflict=0.2,
                economic=0.2,
                human_interest=0.2,
                morality=0.2,
                responsibility=0.2,
            )

        try:
            # Get primary LLM with fallback
            llm = get_chat_model_with_fallback(temperature=0.0)

            # Bind structured output
            structured_llm = llm.with_structured_output(FramingVector)

            system_msg = SystemMessage(content=FRAMING_SYSTEM_PROMPT)
            user_msg = HumanMessage(
                content=build_framing_user_prompt(publisher, topic, chunks_text),
            )

            # Invoke
            framing_vector = await structured_llm.ainvoke([system_msg, user_msg])
            logger.info("Successfully extracted framing vector", publisher=publisher)

            # Normalize framing vector so it sums to 1.0 (optional, but JS divergence needs a distribution)
            return self._normalize_vector(framing_vector)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Framing extraction failed, returning uniform distribution",
                publisher=publisher,
                error=str(exc),
            )
            return FramingVector(
                conflict=0.2,
                economic=0.2,
                human_interest=0.2,
                morality=0.2,
                responsibility=0.2,
            )

    def _normalize_vector(self, vector: FramingVector) -> FramingVector:
        """Ensure framing vector values are non-negative and sum to 1.0."""
        vals = [
            max(0.0, vector.conflict),
            max(0.0, vector.economic),
            max(0.0, vector.human_interest),
            max(0.0, vector.morality),
            max(0.0, vector.responsibility),
        ]
        total = sum(vals)
        if total <= 0.0:
            return FramingVector(
                conflict=0.2,
                economic=0.2,
                human_interest=0.2,
                morality=0.2,
                responsibility=0.2,
            )

        return FramingVector(
            conflict=round(vals[0] / total, 4),
            economic=round(vals[1] / total, 4),
            human_interest=round(vals[2] / total, 4),
            morality=round(vals[3] / total, 4),
            responsibility=round(vals[4] / total, 4),
        )
