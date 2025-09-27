# report_page.py
import time
import json
import logging
import sys
import streamlit as st
from rag_engine import run_rag_pipeline

# -----------------------------------------------------------------------------
# Navigation helper
# - We first try to import your app's go(); if not available, we provide a local fallback.
# -----------------------------------------------------------------------------
try:
    from app import go as _app_go  # adjust to your main module if needed (e.g., streamlit_app)
except Exception:
    _app_go = None


def go(page: str, **params):
    """Navigate to another logical page and update the URL query parameters."""
    if _app_go is not None:
        return _app_go(page, **params)

    # Local fallback (does not modify your main app)
    st.session_state["route"] = page
    try:
        qp = st.query_params  # Streamlit >= 1.33
        qp.clear()
        qp.update({"page": page, **{k: str(v) for k, v in params.items()}})
    except Exception:
        # Older Streamlit API
        st.experimental_set_query_params(page=page, **{k: str(v) for k, v in params.items()})
    # Avoid an extra rerun; query-param change triggers a rerun anyway.
    st.stop()


# -----------------------------------------------------------------------------
# Eco-themed animated loading screen
# -----------------------------------------------------------------------------
def render_loading_screen(estimated_seconds: int = 24, work_fn=None, *args, **kwargs):
    """
    Eco-themed full-screen overlay loader that:
    - Covers the entire viewport (no underlying page visible)
    - Runs `work_fn(*args, **kwargs)` while the overlay is visible
    - Updates the step line to "Rapport généré" on completion
    - Removes the overlay before returning
    """

    # One placeholder to own the overlay so we can remove it later
    overlay = st.empty()

    # Inject CSS + HTML overlay (full screen, fixed, high z-index)
    overlay.markdown(
        """
        <style>
        /* Make the whole app dark to avoid any flicker on repaint */
        html, body { background: #0A0D0A !important; }
        [data-testid="stAppViewContainer"] { background: #0A0D0A !important; }
        [data-testid="stHeader"], header[role="banner"] { display: none !important; }
        /* Hide the sidebar so nothing peeks from the left */
        [data-testid="stSidebar"] { display: none !important; }

        /* Full-screen overlay */
        #eco-overlay {
          position: fixed;
          inset: 0;                 /* top:0; right:0; bottom:0; left:0 */
          background: #0A0D0A;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 999999;          /* above everything Streamlit renders */
        }

        .eco-spinner {
          width: 120px;
          height: 120px;
          border: 8px solid rgba(46, 204, 113, 0.18);
          border-top-color: #2ECC71;
          border-right-color: rgba(46,204,113,0.28);
          border-radius: 50%;
          animation: spin 1.05s linear infinite;
          box-shadow: 0 0 30px rgba(46, 204, 113, 0.25),
                      inset 0 0 8px rgba(46, 204, 113, 0.12);
        }

        .step-line {
          margin-top: 12px;
          font-size: 1.75rem;
          font-weight: 600;
          color: #A5D6A7;
          text-align: center;
          letter-spacing: 0.2px;
        }

        @keyframes spin { to { transform: rotate(360deg); } }
        </style>

        <div id="eco-overlay">
          <div class="eco-spinner"></div>
          <div id="eco-step" class="step-line">
            PrismAI génère votre rapport stratégique, en toute confidentialité
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Run the heavy work while the overlay is on screen ----
    result = None
    t0 = time.time()
    if work_fn is not None:
        try:
            result = work_fn(*args, **kwargs)
        finally:
            elapsed = int(time.time() - t0)
            # Optional: keep the overlay briefly if your estimate is longer
            # to avoid a jarring instant jump
            pad = max(0, (estimated_seconds or 0) - elapsed)
            if pad:
                time.sleep(min(pad, 1))  # cap padding so it doesn't feel artificial

    # Show completion message very briefly (keeps the UX crisp)
    overlay.markdown(
        """
        <div id="eco-overlay">
          <div class="eco-spinner"></div>
          <div id="eco-step" class="step-line">Rapport généré</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(0.25)

    # Remove overlay so the next view (or navigation) is fully visible
    overlay.empty()
    return result


# -----------------------------------------------------------------------------
# Render page: consume prior form data, print to terminal, show loader
# -----------------------------------------------------------------------------
def render():
    # 1) Get payload from previous page's form (preferred)
    payload = st.session_state.get("report_params", {}).copy()

    # Timestamp for logging
    payload.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

    # -------- Print to terminal (stdout + logging) --------
    print("[report_page] Received form payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    logger = logging.getLogger("report_page")
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # -------- Show the animated eco loading screen WHILE generating the report --------
    # This will display the loader immediately, then run the RAG pipeline.
    result = render_loading_screen(
        estimated_seconds=4,
        work_fn=run_rag_pipeline,
        payload=payload
    )

    # Optionally keep the result for the next page
    if result is not None:
        st.session_state["report_result"] = result

    # -------- Navigate or display result --------
    # Uncomment if you want to jump to another logical page after generation:
    # go("map")  # example
