"""
NewsLens End-to-End Latency Benchmark.

Runs a fixed set of representative queries against the live server and
records actual wall-clock latencies for each pipeline stage.

Usage:
    # Server must be running first:
    #   poetry run uvicorn src.m5_ui.api.server:app --port 8000

    poetry run python scripts/benchmark.py
    poetry run python scripts/benchmark.py --url http://localhost:8000 --runs 5
    poetry run python scripts/benchmark.py --url https://your-render-url.onrender.com

Output:
    Prints a per-query latency table and summary statistics to stdout.
    Writes results to benchmark_results.json for inclusion in the report.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime

import httpx


# ── Representative benchmark queries ─────────────────────────────────────────
BENCHMARK_QUERIES = [
    # (query, expected_intent)
    ("Summarize US-China trade talks across publishers", "CROSS_PUBLISHER_SUMMARY"),
    ("How did Reuters vs Fox News cover the US debt ceiling?", "BIAS_DETECTION"),
    ("Timeline of the Ukraine conflict in 2024", "TIMELINE"),
    ("What is the latest news on AI regulation?", "CROSS_PUBLISHER_SUMMARY"),
    ("Compare BBC and CNN coverage of climate change", "BIAS_DETECTION"),
]


def run_single_query(client: httpx.Client, url: str, query: str) -> dict:
    """Run one query and return timing + metadata."""
    start = time.perf_counter()
    try:
        response = client.post(
            f"{url}/api/analyze",
            json={"query": query},
            timeout=120.0,
        )
        elapsed = time.perf_counter() - start
        if response.status_code == 200:
            data = response.json()
            return {
                "query": query,
                "status": "ok",
                "latency_s": round(elapsed, 2),
                "tier_used": data.get("metadata", {}).get("retrieval_tier_used", "unknown"),
                "intent": data.get("metadata", {}).get("intent_class", "unknown"),
                "n_chunks": data.get("metadata", {}).get("chunks_retrieved", 0),
                "error": None,
            }
        else:
            return {
                "query": query,
                "status": "http_error",
                "latency_s": round(elapsed, 2),
                "tier_used": "n/a",
                "intent": "n/a",
                "n_chunks": 0,
                "error": f"HTTP {response.status_code}",
            }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return {
            "query": query,
            "status": "error",
            "latency_s": round(elapsed, 2),
            "tier_used": "n/a",
            "intent": "n/a",
            "n_chunks": 0,
            "error": str(exc),
        }


def print_table(results: list[dict]) -> None:
    """Print results as a formatted table."""
    print()
    print("=" * 100)
    print(f"{'Query':<52} {'Latency':>9} {'Tier':<12} {'Intent':<28} {'Status'}")
    print("-" * 100)
    for r in results:
        q = r["query"][:50] + ".." if len(r["query"]) > 50 else r["query"]
        print(
            f"{q:<52} {r['latency_s']:>8.2f}s {r['tier_used']:<12} "
            f"{r['intent']:<28} {r['status']}"
        )
    print("=" * 100)


def print_summary(all_results: list[dict]) -> None:
    """Print aggregate statistics."""
    ok = [r for r in all_results if r["status"] == "ok"]
    latencies = [r["latency_s"] for r in ok]

    print()
    print("── Summary ──────────────────────────────────────────────────")
    print(f"  Total queries run : {len(all_results)}")
    print(f"  Successful        : {len(ok)}")
    print(f"  Errors            : {len(all_results) - len(ok)}")
    if latencies:
        print(f"  Mean latency      : {statistics.mean(latencies):.2f}s")
        print(f"  Median latency    : {statistics.median(latencies):.2f}s")
        print(f"  Min / Max         : {min(latencies):.2f}s / {max(latencies):.2f}s")
        if len(latencies) > 1:
            print(f"  Std deviation     : {statistics.stdev(latencies):.2f}s")

    # Tier breakdown
    tiers: dict[str, int] = {}
    for r in ok:
        tiers[r["tier_used"]] = tiers.get(r["tier_used"], 0) + 1
    if tiers:
        print("  Retrieval tiers   :", ", ".join(f"{t}={n}" for t, n in sorted(tiers.items())))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsLens latency benchmark")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="Base URL of the server"
    )
    parser.add_argument(
        "--runs", type=int, default=1, help="Number of benchmark runs (queries × runs)"
    )
    parser.add_argument(
        "--output", default="benchmark_results.json", help="Output JSON file path"
    )
    args = parser.parse_args()

    print(f"NewsLens Benchmark — {args.url}")
    print(f"Queries: {len(BENCHMARK_QUERIES)} × {args.runs} run(s) = "
          f"{len(BENCHMARK_QUERIES) * args.runs} total")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Verify server is up
    try:
        with httpx.Client(timeout=10) as probe:
            probe.get(f"{args.url}/api/health")
    except Exception as exc:
        print(f"\nERROR: Server not reachable at {args.url}: {exc}")
        print("Start the server first: poetry run uvicorn src.m5_ui.api.server:app --port 8000")
        sys.exit(1)

    all_results: list[dict] = []

    with httpx.Client() as client:
        for run_idx in range(args.runs):
            if args.runs > 1:
                print(f"\n── Run {run_idx + 1}/{args.runs} ──")
            for query, expected_intent in BENCHMARK_QUERIES:
                print(f"  → {query[:60]}...", end="", flush=True)
                result = run_single_query(client, args.url, query)
                result["run"] = run_idx + 1
                result["expected_intent"] = expected_intent
                all_results.append(result)
                status = "✓" if result["status"] == "ok" else "✗"
                print(f"\r  {status} [{result['latency_s']:5.1f}s] {query[:60]}")

    print_table(all_results)
    print_summary(all_results)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "server_url": args.url,
        "runs": args.runs,
        "results": all_results,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
