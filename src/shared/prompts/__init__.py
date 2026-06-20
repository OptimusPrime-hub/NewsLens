"""
Unified access to all LLM prompt templates across NewsLens modules.
"""

from src.shared.prompts.crag import CRAG_SYSTEM_PROMPT, build_crag_user_prompt
from src.shared.prompts.explanation import (
    BIAS_EXPLANATION_SYSTEM_PROMPT,
    build_bias_explanation_user_prompt,
)
from src.shared.prompts.framing import FRAMING_SYSTEM_PROMPT, build_framing_user_prompt
from src.shared.prompts.intent import INTENT_SYSTEM_PROMPT, build_intent_user_prompt
from src.shared.prompts.summary import SUMMARY_SYSTEM_PROMPT, build_summary_user_prompt
from src.shared.prompts.timeline import (
    TIMELINE_PREPARATION_SYSTEM_PROMPT,
    build_timeline_user_prompt,
)

__all__ = [
    "CRAG_SYSTEM_PROMPT",
    "build_crag_user_prompt",
    "BIAS_EXPLANATION_SYSTEM_PROMPT",
    "build_bias_explanation_user_prompt",
    "FRAMING_SYSTEM_PROMPT",
    "build_framing_user_prompt",
    "INTENT_SYSTEM_PROMPT",
    "build_intent_user_prompt",
    "SUMMARY_SYSTEM_PROMPT",
    "build_summary_user_prompt",
    "TIMELINE_PREPARATION_SYSTEM_PROMPT",
    "build_timeline_user_prompt",
]

