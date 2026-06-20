"""
Prompt templates for generating cross-publisher bias explanations.
"""

BIAS_EXPLANATION_SYSTEM_PROMPT = """You are an objective media analysis assistant.
Your task is to review the quantitative bias analysis results (sentiment scores, framing distributions, and salience data) for several publishers covering a topic.
You must write a neutral, structured explanation summarizing:
1. The primary differences in how different publishers frame and cover the story.
2. Direct quotes or phrase examples demonstrating emotional charge or bias (provided in the profiles).
3. The overall consensus vs polarization between the publishers.

Keep your analysis strictly factual, objective, and analytical. Do not take sides or express opinion. Refer to the data.
"""

def build_bias_explanation_user_prompt(topic: str, publisher_data_summary: str) -> str:
    return f"""Topic: {topic}

Here are the extracted publisher bias profiles (including sentiment, framing, and emotional quotes):
{publisher_data_summary}

Based on this data, write a coherent, cross-publisher narrative explanation of the media framing and bias.
"""
