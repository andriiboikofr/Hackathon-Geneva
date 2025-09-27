from pathlib import Path
import os, re, uuid, random, textwrap, datetime
from typing import Dict, List, Optional, Tuple

import chromadb
try:
    from chromadb.config import Settings
except Exception:
    from chromadb import Settings

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ---- Paths must match ingestion ----
ROOT_DIR = Path.cwd()
DATA_ROOT = ROOT_DIR / "data"
PERSIST_ROOT = DATA_ROOT / "chroma_dbs"

# Chroma collections (created during ingestion)
COLLECTION_SLUGS = {
    "education": "education",
    "healthcare": "healthcare",
    "private_sector": "private_sector",
    "state": "state",
}

# Embedding model used at ingestion time (keep identical)
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)

# Retrieval params
TOP_K = 6
MAX_CONTEXT_CHARS = 9000

# Output dir for reports
REPORTS_DIR = DATA_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Optional extra context you may provide (if empty, we synthesize)
education_sector = " "
private_sector  = " "
healthcare_sector = " "
state_sector = " "

# Optional: Swiss legal references/excerpts (paste your law text; left blank uses a generic disclaimer)
swiss_law = ""

def open_collection(slug: str):
    persist_dir = PERSIST_ROOT / slug
    if not persist_dir.exists():
        raise FileNotFoundError(f"Chroma persist dir not found: {persist_dir}")
    client = chromadb.Client(Settings(
        anonymized_telemetry=False,
        allow_reset=True,
        is_persistent=True,
        persist_directory=str(persist_dir),
    ))
    return client.get_collection(name=slug, embedding_function=embedding_fn)

COLLECTIONS = {k: open_collection(v) for k, v in COLLECTION_SLUGS.items()}
print("✅ Opened collections:", ", ".join([f"{k}→{v.name}" for k,v in COLLECTIONS.items()]))


import re
from typing import Tuple, Dict, Any

def clean_text(x: str) -> str:
    if not x:
        return ""
    # Normalize line endings & whitespace
    x = x.replace("\r\n", "\n").replace("\r", "\n")
    # Remove control chars except \n and \t
    x = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", x)
    # Collapse excessive spaces/newlines
    x = re.sub(r"[ \t]+", " ", x)
    x = re.sub(r"\n{3,}", "\n\n", x)
    return x.strip()

def get_streamlit_data_and_info_building_and_scenario() -> Tuple[str, str, Dict[str, Any]]:
    """
    Your implementation should load:
      - scenario: str
      - selected_sector: str (one of 'education','healthcare','private_sector','state')
      - sector_buildings_information: dict or str (key facts for the stakeholder/building(s))

    Return ["scenario", "selected_sector", "sector_buildings_information"]
    """
    # --- you fill this with your CSV/Streamlit state reads ---
    scenario = "..."                      # str
    selected_sector = "education"         # str
    sector_buildings_information = {...}  # dict or str
    # Clean text fields
    scenario = clean_text(scenario)
    if isinstance(sector_buildings_information, str):
        sector_buildings_information = clean_text(sector_buildings_information)  # ok if you store as str
    return scenario, selected_sector, sector_buildings_information
