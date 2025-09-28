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
from typing import Tuple, Dict, Any
def parse_report_session_data_to_dict(file_path='report_session_data.txt'):
    parsed_data = {
        'scenario': None,
        'sectors': None,
        'reduction_start': None,
        'reduction_end': None,
        'organization': None
    }

    with open(file_path, 'r') as file:
        lines = file.readlines()

    for line in lines:
        if line.startswith("reduction_supply:"):
            parsed_data['scenario'] = line.split(":", 1)[1].strip()
        elif line.startswith("industry:"):
            parsed_data['sectors'] = line.split(":", 1)[1].strip()
        elif line.startswith("reduction_start:"):
            parsed_data['reduction_start'] = line.split(":", 1)[1].strip()
        elif line.startswith("reduction_end:"):
            parsed_data['reduction_end'] = line.split(":", 1)[1].strip()
        elif line.startswith("organization:"):
            parsed_data['organization'] = line.split(":", 1)[1].strip()

    return parsed_data

def retrieve_topk(sector: str, question: str, sc_text: str, top_k: int = TOP_K):
    if sector not in COLLECTIONS:
        raise ValueError(f"Unknown sector '{sector}'. Choose among {list(COLLECTIONS.keys())}.")
    col = COLLECTIONS[sector]

    # Compose concise query (model context will include richer blocks)
    q = f"{question}\nScénario: {sc_text}\nRéférences légales: {('fourni' if swiss_law.strip() else 'non fourni')}"
    out = col.query(
        query_texts=[q],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    docs = out.get("documents", [[]])[0]
    metas = out.get("metadatas", [[]])[0]
    dists = out.get("distances", [[]])[0]
    return {
        "sector": sector,
        "scenario": sc_text,
        "question": question,
        "chunks": list(zip(docs, metas, dists)),
    }

def truncate_chunks(chunks: List[Tuple[str, Dict, float]], max_chars: int = MAX_CONTEXT_CHARS):
    acc, total = [], 0
    seen = set()
    for txt, meta, dist in chunks:
        # Dedup by file+chunk
        key = (meta.get("filename"), meta.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        t = (txt or "").strip()
        if not t:
            continue
        if total + len(t) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                acc.append((t[:remaining], meta, dist))
            break
        acc.append((t, meta, dist))
        total += len(t)
    return acc

def build_markdown_prompt(sector: str, payload: Dict) -> Tuple[str, str, List[str]]:
    """
    Returns (system_msg, user_msg, sources_list)
    """
    sc_text    = payload["scenario"]
    question   = payload["question"]
    chunks     = truncate_chunks(payload["chunks"], MAX_CONTEXT_CHARS)

    # Build context block + citations we’ll also append after generation
    context_block = []
    sources = []
    for i, (txt, meta, dist) in enumerate(chunks, start=1):
        context_block.append(f"[EXTRAIT {i} — {meta.get('filename')}#chunk{meta.get('chunk_index')} — d={dist:.3f}]\n{txt}")
        sources.append(f"{meta.get('filename')}#chunk{meta.get('chunk_index')} (d={dist:.3f})")
    context_block = "\n\n".join(context_block) if context_block else "(Aucun extrait disponible)"

    # Legal block (use provided text; otherwise add a neutral disclaimer)
    swiss_law_block = swiss_law.strip() if swiss_law.strip() else (
        "⚠️ Aucun extrait légal fourni. Résumer ici les bases légales suisses/cantonales pertinentes "
        "(p.ex. politique énergétique fédérale, mesures de pénurie, obligations des grands consommateurs, "
        "plans de délestage/OSTRAL), et préciser que l’interprétation doit être validée par les conseillers juridiques."
    )

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = f"Rapport de sobriété énergétique — {sector.capitalize()} — Scénario: {sc_text}"

    system_msg = (
        "Tu es un assistant RAG suisse spécialisé en énergie. Tu est un distributeur d'énergie qui conseille des clients. Tu produis STRICTEMENT un rapport Markdown en français suisse, "
        "structuré et actionnable, en t’appuyant uniquement sur le contexte fourni."
    )

    # The model must output a well-formed .md with YAML + 4 parts
    user_msg = f"""
Tu dois produire un fichier **Markdown (.md)** complet, avec la structure EXACTE suivante:

1) Un en-tête H1 avec le title:
# {title}

2) Un bloc **métadonnées** sous forme de liste:
- **Secteur**: {sector}
- **Scénario**: {sc_text}
- **Date**: {today}

3) **Partie 1 — Base légale**
Explique clairement le cadre légal suisse/cantonal applicable au secteur (objectif: montrer que le fournisseur d'énergie a le droit d'exiger des réductions en cas de tension).
Utilise **uniquement** le bloc 'Références légales' ci-dessous et/ou les extraits RAG.
Si des lois précises ne sont pas fournies, rédige une synthèse prudente avec un avertissement.

4) **Partie 2 — Données motivantes (scénario)**
Présente des **données fictives mais plausibles**, alignées sur le scénario ("minimum", "moyen", "maximum").
Les mettres dans une table et indiqué leurs valeurs et leurs unité (kWh, L, ...) Inclure indicateurs (pics, kWh/MWh, émissions CO₂).


5) **Partie 3 — Informations spécifiques au domaine**
Adapter aux spécificités du secteur (processus, horaires, équipements critiques, contraintes opérationnelles, dépendances).


6) **Partie 4 — Recommandations (liste à puces)**
List 3 à 5 **actions concrètes** priorisées, chiffrées si possible, estimation de l'impact attendu.

7) **Sources**
Liste les fichiers et chunks utilisés (tels que fournis dans les extraits). Ne pas inventer de sources.

Règles:
- Français suisse, ton en fonction du secteur. Soit plus simple et compréhensible pour le secteur de l'education, plus pédagogue. Tandis que pour le secteur privé plus orienté valeur ajouté et revenue.
Pour le secteur de la santé soit plus précis mais aussi conciencieux de leur occupation : les hopitaux sont souvent les derniers a être atteint par des reductions energetique.
- Pas d'hallucination: ne pas affirmer des références légales non présentes dans le contexte.
- Respecte l’ordre des sections, la mise en forme, et la concision utile.

=== CONTEXTE ===
Question:
{question}

Références légales (texte brut fourni ou placeholder):
{ """ 
    "Responsabilité  (mise à jour au 27.09.2025) En cas d’activation par la Confédération de mesures OSTRAL, deux régimes de contingentement peuvent s’appliquer selon l’urgence fixée au niveau fédéral : contingentement “moyen terme” (MT) et contingentement “immédiat” (IM). 1. MT (période généralement mensuelle) : SIG, en tant que gestionnaire de réseau de distribution (GRD) compétent, calcule le contingent mensuel de chaque grand consommateur et notifie la décision au nom du domaine « Énergie » de l’Approvisionnement économique du pays. SIG est responsable du calcul, de la notification et du contrôle du respect du contingent sur son réseau. 2. IM (période journalière) : le grand consommateur (p. ex. votre hôpital) calcule lui-même son contingent journalier selon la méthode prescrite par la Confédération/AES-OSTRAL, tient les preuves (relevés, profil ¼ h, justificatifs d’abattement) et respecte les limites communiquées. SIG contrôle et peut exiger les justificatifs. L’autorité cantonale compétente (p. ex. OCBA) appuie la mise en œuvre et l’exécution sur le territoire genevois.



Dans les deux régimes, le cadre juridique (ordonnances fédérales et décisions du domaine « Énergie ») fait foi. SIG est responsable de l’exécution sur son réseau (calculs, notifications, contrôles, éventuels délestages sur ordre fédéral) et l’établissement raccordé est responsable du respect des obligations qui lui sont notifiées (réduction de charge, preuves, organisation interne). Les installations critiques (p. ex. soins intensifs) doivent planifier des mesures de réduction compatibles avec la sécurité; des protections techniques peuvent exister mais n’impliquent pas d’exemption générale.

Le présent rapport est un appui opérationnel pour préparer votre établissement ; il ne remplace pas les décisions individuelles ni les ordonnances fédérales qui prévalent. SIG actualise ses consignes sur sig-ge.ch dès réception d’instructions fédérales/cantonales ; seule la décision qui vous est notifiée (et ses annexes techniques) est juridiquement contraignante.
Référence interne SIG : OST25-Resp-Hospitals-1.0"""
}

Extraits RAG:
{context_block}
""".strip()

    return system_msg, user_msg, sources

import openai
import os
os.environ["OPENAI_API_KEY"] = "a5FhEQVNJ5N7kUPbqAoqYH5QPlPc"

APERTUS_BASE_URL = "https://api.swisscom.com/layer/swiss-ai-weeks/apertus-70b/v1"
APERTUS_MODEL    = "swiss-ai/Apertus-70B"

def get_apertus_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing OPENAI_API_KEY env var for Apertus API.")
    return openai.OpenAI(api_key=api_key, base_url=APERTUS_BASE_URL)

def call_apertus_stream(system_msg: str, user_msg: str) -> str:
    client = get_apertus_client()
    stream = client.chat.completions.create(
        model=APERTUS_MODEL,
        messages=[{"role": "system", "content": system_msg},
                  {"role": "user", "content": user_msg}],
        temperature=0.2,
        max_tokens=1200,
        stream=True,
    )
    full = []
    for chunk in stream:
        delta = getattr(chunk.choices[0].delta, "content", None)
        if delta:
            print(delta, end="", flush=True)
            full.append(delta)
    print()
    return "".join(full)

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def save_report_md(sector: str, scenario_text: str, md_text: str) -> Path:
    out_dir = REPORTS_DIR / sector
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}__{slugify(sector)}__{slugify(scenario_text[:40])}.md"
    path = out_dir / fname
    path.write_text(md_text, encoding="utf-8")
    return path

def generate_report(sector: str, question: str, scenario_choice: str, top_k: int = TOP_K) -> Path:
    sc = scenario_choice  # Use the provided scenario directly
    payload = retrieve_topk(sector, question, sc, top_k=top_k)
    system_msg, user_msg, sources = build_markdown_prompt(sector, payload)

    print(f"\n--- Generating report for sector='{sector}', scenario='{sc}' ---\n")
    md = call_apertus_stream(system_msg, user_msg)

    # Ensure a Sources footer
    if "## Sources" not in md and "**Sources**" not in md:
        md += "\n\n## Sources\n"
        md += "\n".join([f"- {s}" for s in (sources or ["(aucune source RAG)"])])

    out_path = save_report_md(sector, sc, md)
    print(f"\n✅ Saved report → {out_path}")
    return out_path

# First, parse the session data
parsed_data = parse_report_session_data_to_dict("report_session_data.txt")

# Extract values
sector = parsed_data["sectors"].lower()
scenario = parsed_data["scenario"]
question = f"Atteindre {scenario}% de réduction sans perturber les cours ni la sécurité des élèves."

# Call the report generation function
report_path = generate_report(
    sector=sector,
    question=question,
    scenario_choice=scenario,  # You can make this dynamic if needed
    top_k=6
)
