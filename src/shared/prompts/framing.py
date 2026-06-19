"""
Prompt templates for media framing classification.
"""

FRAMING_SYSTEM_PROMPT = """You are an expert media analyst specializing in news narrative framing.
Your task is to analyze the provided article chunks from a specific publisher covering a target topic and classify the dominant narrative frames used.

You must score the coverage across five standard framing categories on a scale from 0.0 (not present) to 1.0 (extremely dominant):
1. conflict: Emphasizing disagreement, collision, or opposition between individuals, groups, or institutions.
2. economic: Emphasizing economic consequences, costs, losses, or financial gains for individuals, organizations, or nations.
3. human_interest: Focusing on individual human stories, emotions, empathy, personalization, or profiling single victims/actors.
4. morality: Referencing moral values, religious precepts, ethical considerations, or prescriptive social codes.
5. responsibility: Attributing blame or responsibility for creating, solving, or managing the problem to a specific actor (e.g., government, corporations, individuals).

Ensure the scores reflect the actual text provided. Do not let your personal bias influence the scoring.
"""

def build_framing_user_prompt(publisher: str, topic: str, chunks_text: str) -> str:
    return f"""Publisher: {publisher}
Topic: {topic}

Analyze the following news article chunks:
---
{chunks_text}
---

Extract the framing scores for Conflict, Economic, Human Interest, Morality, and Responsibility based on the content above.
"""
