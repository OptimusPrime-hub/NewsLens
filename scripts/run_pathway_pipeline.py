import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now your imports will work!
from src.m0_ingestion.pipeline import build_pipeline
import pathway as pw
from src.m0_ingestion.pipeline import build_pipeline

if __name__ == "__main__":
    print("🚀 Starting NewsLens Pathway Ingestion Engine (M0)...")
    build_pipeline()
    pw.run()