"""
Persona Lab — Streamlit UI (M2)
Runs entirely on mocks (USE_MOCKS = True in persona_lab_core.py) — $0.
At M3: teammate flips USE_MOCKS = False in core, UI needs zero changes.
"""

import time
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

# ── import core pipeline ──────────────────────────────────────────────────────
# In Colab: the core file lives in the same directory.
# Make sure persona_lab_core.py is in the same folder as this file.
from persona_lab_core import (
    run_persona_panel, run_moderator, run_strategist, PERSONAS
)

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Persona Lab",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* page background */
  .stApp { background: #0F1923; }

  /* hide default streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1100px; }

  /* hero title */
  .hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3rem; font-weight: 700;
    background: linear-gradient(135deg, #FFFFFF 0%, #048A81 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
  }
  .hero-sub {
    color: #6B7D8A; font-size: 1rem; font-weight: 400; margin-bottom: 2rem;
  }

  /* input area */
  .stTextArea textarea {
    background: #1A2630 !important;
    border: 1px solid #2E4057 !important;
    border-radius: 10px !important;
    color: #E8EDF0 !important;
    font-size: 0.95rem !important;
    padding: 0.75rem !important;
  }
  .stTextArea textarea:focus {
    border-color: #048A81 !important;
    box-shadow: 0 0 0 2px rgba(4,138,129,0.2) !important;
  }

  /* run button */
  .stButton > button {
    background: linear-gradient(135deg, #048A81, #2E4057) !important;
    color: white !important; font-weight: 600 !important;
    border: none !important; border-radius: 8px !important;
    padding: 0.6rem 2rem !important; font-size: 1rem !important;
    transition: opacity 0.2s;
  }
  .stButton > button:hover { opacity: 0.85 !important; }

  /* sentiment badge */
  .badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 12px; font-size: 0.72rem; font-weight: 600;
    letter-spacing: 0.04em; text-transform: uppercase;
  }
  .badge-positive { background: rgba(39,174,96,0.15); color: #27AE60; }
  .badge-mixed    { background: rgba(243,156,18,0.15); color: #F39C12; }
  .badge-negative { background: rgba(231,76,60,0.15);  color: #E74C3C; }

  /* persona card */
  .persona-card {
    background: #1A2630;
    border: 1px solid #2E4057;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s;
  }
  .persona-card:hover { border-color: #048A81; }
  .persona-name {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600; font-size: 0.9rem; color: #C8D6DF;
    margin-bottom: 0.4rem;
  }
  .persona-reaction { color: #8FA3B0; font-size: 0.88rem; line-height: 1.55; }
  .objection-label { color: #4A6070; font-size: 0.75rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.6rem; }
  .objection-text  { color: #C0392B; font-size: 0.85rem; margin-top: 0.1rem; }

  /* theme card */
  .theme-card {
    background: #1A2630; border: 1px solid #2E4057;
    border-left: 3px solid #048A81;
    border-radius: 8px; padding: 0.85rem 1rem; margin-bottom: 0.6rem;
  }
  .theme-name  { color: #FFFFFF; font-weight: 600; font-size: 0.9rem; }
  .theme-names { color: #6B7D8A; font-size: 0.78rem; margin-top: 0.2rem; }
  .theme-tension { color: #F39C12; font-size: 0.82rem; margin-top: 0.3rem; }

  /* risk box */
  .risk-box {
    background: rgba(231,76,60,0.08); border: 1px solid rgba(231,76,60,0.25);
    border-radius: 8px; padding: 0.75rem 1rem; margin-top: 0.5rem;
  }
  .risk-label { color: #E74C3C; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; }
  .risk-text  { color: #C8D6DF; font-size: 0.88rem; margin-top: 0.2rem; }

  /* consensus box */
  .consensus-box {
    background: rgba(4,138,129,0.08); border: 1px solid rgba(4,138,129,0.25);
    border-radius: 8px; padding: 0.75rem 1rem; margin-top: 0.5rem;
  }
  .consensus-label { color: #048A81; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em; }
  .consensus-text  { color: #C8D6DF; font-size: 0.88rem; margin-top: 0.2rem; }

  /* strategy box */
  .strategy-box {
    background: #1A2630; border: 1px solid #2E4057;
    border-top: 3px solid #048A81;
    border-radius: 8px; padding: 1.2rem 1.4rem;
  }
  .strategy-item {
    display: flex; align-items: flex-start; gap: 0.6rem;
    color: #C8D6DF; font-size: 0.9rem; line-height: 1.6;
    padding: 0.35rem 0;
  }
  .strategy-item + .strategy-item { border-top: 1px solid rgba(46,64,87,0.4); }
  .strategy-bullet { color: #048A81; font-size: 0.95rem; line-height: 1.5; flex-shrink: 0; }

  /* section label */
  .section-label {
    font-family: 'Space Grotesk', sans-serif;
    color: #4A6070; font-size: 0.75rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 0.6rem; margin-top: 1.6rem;
  }

  /* demo mode banner */
  .demo-banner {
    background: rgba(243,156,18,0.1); border: 1px solid rgba(243,156,18,0.3);
    border-radius: 8px; padding: 0.5rem 1rem;
    color: #F39C12; font-size: 0.82rem; margin-bottom: 1rem;
  }

  /* divider */
  hr { border: none; border-top: 1px solid #2E4057; margin: 1.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── demo mode seed ────────────────────────────────────────────────────────────
DEMO_IDEA = "A subscription app that turns your grocery receipts into weekly meal plans."

DEMO_CACHE = None  # populated on first demo run, reused after

# ── helpers ───────────────────────────────────────────────────────────────────
SENTIMENT_EMOJI = {"positive": "🟢", "mixed": "🟡", "negative": "🔴"}

def badge_html(sentiment):
    return f'<span class="badge badge-{sentiment}">{SENTIMENT_EMOJI.get(sentiment,"")} {sentiment}</span>'

def persona_card_html(r):
    return f"""
<div class="persona-card">
  <div class="persona-name">{r['persona']} &nbsp; {badge_html(r['sentiment'])}</div>
  <div class="persona-reaction">{r['reaction']}</div>
  <div class="objection-label">Key objection</div>
  <div class="objection-text">"{r['key_objection']}"</div>
</div>"""

def theme_card_html(t):
    names = ", ".join(t.get("supported_by", []))
    return f"""
<div class="theme-card">
  <div class="theme-name">{t['theme']}</div>
  <div class="theme-names">Raised by: {names}</div>
  <div class="theme-tension">Tension: {t.get('tension','')}</div>
</div>"""

def strategy_html(strategy):
    """Render strategy as clean bullet rows, whether it uses '-', '*', or newlines."""
    lines = [ln.strip().lstrip("-*\u2022 ").strip()
             for ln in strategy.replace(" - ", "\n- ").splitlines()
             if ln.strip().lstrip("-*\u2022 ").strip()]
    items = "".join(
        f'<div class="strategy-item"><span class="strategy-bullet">&#9656;</span><span>{ln}</span></div>'
        for ln in lines
    )
    return f'<div class="strategy-box">{items}</div>'

# ── session state ─────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.session_state.result = None
if "running" not in st.session_state:
    st.session_state.running = False

# ── layout ────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">Persona Lab</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Drop in any idea. Watch five distinct personas react — and disagree.</div>', unsafe_allow_html=True)

# sidebar controls
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    demo_mode = st.toggle("Demo mode", value=False,
        help="Uses a seeded example — no live API calls. Safe for presentations.")
    st.markdown("---")
    st.markdown("**Model routing**")
    st.markdown("🟢 Personas → Gemini Flash-Lite")
    st.markdown("🟡 Moderator → GPT-4o-mini")
    st.markdown("🔵 Strategist → Claude Haiku")
    st.markdown("---")
    st.caption("Cost: $0 (mocks) · $0–3 total (live)")

# input
idea_input = st.text_area(
    label="Your idea",
    placeholder="e.g. A subscription app that turns grocery receipts into weekly meal plans...",
    height=100,
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 5])
with col1:
    run_clicked = st.button("Run focus group →", use_container_width=True)

# ── run logic ─────────────────────────────────────────────────────────────────
if run_clicked:
    idea = DEMO_IDEA if demo_mode else idea_input.strip()

    if not idea:
        st.warning("Enter an idea first.")
    else:
        if demo_mode and DEMO_CACHE is not None:
            st.session_state.result = DEMO_CACHE
        else:
            st.session_state.result = None
            st.session_state.running = True

            # streaming persona panel — cards appear as each one finishes
            st.markdown('<div class="section-label">Panel reactions</div>', unsafe_allow_html=True)

            if demo_mode:
                st.markdown('<div class="demo-banner">⚡ Demo mode — showing seeded example, no live API calls.</div>', unsafe_allow_html=True)

            card_slots = [st.empty() for _ in PERSONAS]
            reactions = [None] * len(PERSONAS)

            def run_one(i_and_persona):
                i, p = i_and_persona
                from persona_lab_core import (
                    call_llm, PERSONA_SYSTEM_TEMPLATE, _mock_persona_for, _safe_json
                )
                system = PERSONA_SYSTEM_TEMPLATE.format(
                    name=p["name"], stance=p["stance"],
                    priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea=idea)
                raw = call_llm("persona", system, idea, _mock_persona_for(p["name"]), idea)
                return i, _safe_json(raw, fallback={"persona": p["name"], "reaction": raw,
                                     "sentiment": "mixed", "key_objection": "n/a"})

            # show loading placeholders
            for slot in card_slots:
                slot.markdown('<div class="persona-card" style="opacity:0.3">⏳ Thinking...</div>',
                              unsafe_allow_html=True)

            # stream results as they arrive
            with ThreadPoolExecutor(max_workers=len(PERSONAS)) as ex:
                futures = {ex.submit(run_one, (i, p)): i for i, p in enumerate(PERSONAS)}
                import concurrent.futures
                for future in concurrent.futures.as_completed(futures):
                    i, r = future.result()
                    reactions[i] = r
                    card_slots[i].markdown(persona_card_html(r), unsafe_allow_html=True)

            # moderator
            st.markdown('<div class="section-label">Moderator — themes & tensions</div>', unsafe_allow_html=True)
            with st.spinner("Moderator clustering reactions..."):
                moderation = run_moderator(reactions)

            for t in moderation.get("themes", []):
                st.markdown(theme_card_html(t), unsafe_allow_html=True)

            if moderation.get("consensus"):
                st.markdown(f"""<div class="consensus-box">
                  <div class="consensus-label">Consensus</div>
                  <div class="consensus-text">{moderation['consensus']}</div>
                </div>""", unsafe_allow_html=True)

            if moderation.get("biggest_risk"):
                st.markdown(f"""<div class="risk-box">
                  <div class="risk-label">Biggest risk</div>
                  <div class="risk-text">{moderation['biggest_risk']}</div>
                </div>""", unsafe_allow_html=True)

            # strategist
            st.markdown('<div class="section-label">Strategist — recommendations</div>', unsafe_allow_html=True)
            with st.spinner("Strategist synthesizing..."):
                strategy = run_strategist(moderation)

            st.markdown(strategy_html(strategy), unsafe_allow_html=True)

            result = {"idea": idea, "reactions": reactions,
                      "moderation": moderation, "strategy": strategy}
            st.session_state.result = result
            if demo_mode:
                DEMO_CACHE = result
            st.session_state.running = False

# ── show cached result (re-render without re-running) ─────────────────────────
elif st.session_state.result:
    out = st.session_state.result

    st.markdown('<div class="section-label">Panel reactions</div>', unsafe_allow_html=True)
    for r in out["reactions"]:
        st.markdown(persona_card_html(r), unsafe_allow_html=True)

    st.markdown('<div class="section-label">Moderator — themes & tensions</div>', unsafe_allow_html=True)
    for t in out["moderation"].get("themes", []):
        st.markdown(theme_card_html(t), unsafe_allow_html=True)

    if out["moderation"].get("consensus"):
        st.markdown(f"""<div class="consensus-box">
          <div class="consensus-label">Consensus</div>
          <div class="consensus-text">{out['moderation']['consensus']}</div>
        </div>""", unsafe_allow_html=True)

    if out["moderation"].get("biggest_risk"):
        st.markdown(f"""<div class="risk-box">
          <div class="risk-label">Biggest risk</div>
          <div class="risk-text">{out['moderation']['biggest_risk']}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Strategist — recommendations</div>', unsafe_allow_html=True)
    st.markdown(strategy_html(out['strategy']), unsafe_allow_html=True)
