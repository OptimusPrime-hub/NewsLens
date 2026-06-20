import os, json
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

from src.m1_intent.classifier import IntentClassifier
from src.m0_ingestion.pipeline import get_pipeline
from groq import Groq

def main():
    user_query = input("Ask a question about the news: ")

    # M1 first — classify intent so we can fetch topic-specific articles
    classifier = IntentClassifier()
    payload = classifier.classify(user_query)
    print(f"\n[M1] Intent:     {payload.intent.value}")
    print(f"[M1] Confidence: {payload.confidence:.2f}")
    print(f"[M1] Entities:   {payload.entities}")
    print(f"[M1] Publishers: {payload.publishers}")
    print(f"[M1] Keywords:   {payload.topic_keywords}")

    # M0: fetch articles targeted at the actual query topic
    # Use extracted keywords + entities for a focused NewsAPI fetch
    search_query = " ".join(payload.topic_keywords[:4] or payload.entities[:3] or ["world news"])
    print(f"\n[M0] Fetching live articles for: '{search_query}'")
    pipeline = get_pipeline(query=search_query)
    pipeline._poll_once()
    print(f"[M0] Ingested {pipeline.chunk_count} chunks from live sources")

    embedder = pipeline.embedder
    q_vec = embedder.embed_texts([user_query])[0].tolist()
    results = pipeline.similarity_search(q_vec, top_k=8)

    if not results:
        print("\n[M0] No relevant chunks found.")
        return

    print(f"[M0] Retrieved {len(results)} chunks (top score: {results[0][1]:.3f})")

    # Show which publishers contributed
    publishers_used = list({chunk.publisher for chunk, _ in results})
    print(f"[M0] Publishers: {publishers_used}")

    context_text = "\n\n".join(
        f"[{chunk.publisher} | score={score:.2f}] {chunk.chunk_text[:500]}"
        for chunk, score in results
    )

    intent_instruction = {
        "BIAS_DETECTION": (
            "Compare how different publishers frame this topic. "
            "Note differences in tone, word choice, and what each emphasizes or omits. "
            "Give a bias score per publisher (positive/negative framing)."
        ),
        "TIMELINE": (
            "Extract ALL events mentioned across sources and arrange them in strict chronological order. "
            "For each event include: date (if mentioned), what happened, and which publisher reported it. "
            "Flag any contradictions between sources."
        ),
        "CROSS_PUBLISHER_SUMMARY": (
            "Summarize the key facts all sources agree on. "
            "Then list points where sources diverge or contradict. "
            "End with a confidence score (0-1) for how consistent the overall coverage is."
        ),
    }.get(payload.intent.value, "Summarize the news.")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise investigative news analyst. "
                    "Use ONLY the provided sources. Cite publisher names when referencing facts. "
                    "Never hallucinate facts not present in the sources."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Task: {intent_instruction}\n\n"
                    f"Sources:\n{context_text}\n\n"
                    f"Question: {user_query}"
                )
            }
        ],
        temperature=0.1,  # low temp = more factual, less hallucination
        max_tokens=1024,
    )

    print("\n--- FINAL ANSWER ---")
    print(f"(Intent: {payload.intent.value} | Publishers: {publishers_used})")
    print(response.choices[0].message.content)

if __name__ == "__main__":
    main()
