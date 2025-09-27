# rag_engine.py

def run_rag_pipeline(payload: dict):
    """
    Receives the payload from the Streamlit page and prints it.
    Later, this will trigger the actual RAG logic.
    """
    print("[rag_engine] Received payload:")
    for key, value in payload.items():
        print(f"  {key}: {value}")


