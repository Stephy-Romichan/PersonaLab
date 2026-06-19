"""
Persona Lab — Streamlit UI ("Light Lab" theme)
A sunlit, high-end research-facility aesthetic: glassmorphism, crisp grid,
centered workspace, left-aligned sidebar, vibrant clinical accents.
Output contract unchanged: works with mock or live backend with no edits.
"""

import concurrent.futures
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

from persona_lab_core import (
    run_persona_panel, run_moderator, run_strategist, PERSONAS,
    call_llm, PERSONA_SYSTEM_TEMPLATE, _mock_persona_for, _safe_json,
)

st.set_page_config(page_title="Persona Lab", page_icon="🧪", layout="wide",
                   initial_sidebar_state="expanded")

# persona identity colors (cyan / green / amber family + complements)
PERSONA_COLORS = [
    {"bg": "#FFF5F5", "border": "#FA5252", "chip": "#FA5252", "emoji": "💸"},
    {"bg": "#FFF9DB", "border": "#F59F00", "chip": "#F59F00", "emoji": "🚀"},
    {"bg": "#E6FCF5", "border": "#0CA678", "chip": "#0CA678", "emoji": "🏢"},
    {"bg": "#E7F5FF", "border": "#1098AD", "chip": "#1098AD", "emoji": "🛡️"},
    {"bg": "#F3F0FF", "border": "#7048E8", "chip": "#7048E8", "emoji": "⏱️"},
    {"bg": "#FFF0F6", "border": "#E64980", "chip": "#E64980", "emoji": "🎯"},
]
def color_for(i): return PERSONA_COLORS[i % len(PERSONA_COLORS)]

SENTIMENT = {
    "positive": {"label": "Positive", "color": "#0CA678", "bg": "#E6FCF5", "dot": "●"},
    "mixed":    {"label": "Mixed",    "color": "#F59F00", "bg": "#FFF9DB", "dot": "●"},
    "negative": {"label": "Negative", "color": "#FA5252", "bg": "#FFF5F5", "dot": "●"},
}

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

  /* ---- base: sunlit lab ---- */
  .stApp {
    background:
      radial-gradient(1200px 500px at 78% -10%, rgba(16,152,173,0.07), transparent 60%),
      radial-gradient(900px 400px at 10% 0%, rgba(12,166,120,0.06), transparent 55%),
      #F8F9FA;
    color: #1A202C;
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
  }
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 880px; }

  /* faint lab watermark behind the whole workspace */
  .stApp::before {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image:
      url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'><g fill='none' stroke='%23CED4DA' stroke-width='1.4' opacity='0.30'><path d='M52 18h16M56 18v20L44 74a6 6 0 0 0 6 8h20a6 6 0 0 0 6-8L64 38V18'/><circle cx='58' cy='70' r='2'/><circle cx='64' cy='64' r='1.6'/></g></svg>");
    background-repeat: no-repeat; background-position: 90% 78%; background-size: 220px;
    opacity: 0.7;
  }
  .block-container, section[data-testid="stSidebar"] { position: relative; z-index: 1; }

  /* ---- sidebar: frosted glassware ---- */
  section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.65) !important;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border-right: 1px solid #E9ECEF;
  }
  section[data-testid="stSidebar"] * { color: #1A202C; }
  .side-title { font-weight: 800; font-size: 1.05rem; letter-spacing: -0.01em; margin-bottom: 0.2rem; }
  .side-sub { color: #868E96; font-size: 0.78rem; margin-bottom: 0.8rem; }
  .route-row {
    display:flex; align-items:center; gap:0.55rem; padding:0.5rem 0.65rem; margin:0.3rem 0;
    background:#fff; border:1px solid #E9ECEF; border-radius:8px; font-size:0.82rem;
  }
  .route-row .tag { margin-left:auto; font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#1098AD; background:#E7F5FF; padding:2px 7px; border-radius:5px; }

  /* ---- hero ---- */
  .hero {
    position: relative; background: rgba(255,255,255,0.7);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border: 1px solid #E9ECEF; border-radius: 16px; padding: 1.8rem 1.8rem 1.6rem;
    box-shadow: 0 10px 30px rgba(26,32,44,0.06); text-align: center; overflow: hidden;
    margin-bottom: 1.3rem;
  }
  .hero-badge {
    display:inline-flex; align-items:center; gap:0.4rem; background:#E7F5FF; color:#1098AD;
    font-size:0.7rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase;
    padding:5px 13px; border-radius:20px; font-family:'JetBrains Mono',monospace;
  }
  .hero-title {
    font-size:3rem; font-weight:800; letter-spacing:-0.03em; color:#1A202C;
    margin:0.6rem 0 0; line-height:1.05;
    display:flex; align-items:baseline; justify-content:center; gap:0.7rem;
  }
  .hero-title .accent { color:#1098AD; }
  .hero-sub { color:#495057; font-size:1.02rem; margin-top:0.5rem; }
  .hero-deco { position:absolute; opacity:0.55; pointer-events:none; }
  .hero-deco.a  { top:14px;  left:18px; animation: drift 6s ease-in-out infinite; }
  .hero-deco.b  { bottom:12px; right:20px; animation: drift 7s ease-in-out infinite 0.5s; }
  .hero-deco.c  { top:50px;  left:64px; animation: drift 6.5s ease-in-out infinite 0.2s; }
  .hero-deco.d  { top:16px;  right:70px; animation: drift 5.6s ease-in-out infinite 0.8s; }
  .hero-deco.e  { bottom:14px; left:26px; animation: drift 7.4s ease-in-out infinite 0.3s; }
  .hero-deco.f  { top:54px;  right:24px; animation: drift 6.2s ease-in-out infinite 0.6s; }
  .hero-deco.g  { bottom:46px; right:78px; animation: drift 6.8s ease-in-out infinite 0.1s; }
  @keyframes drift { 0%,100%{transform:translateY(0) rotate(-2deg)} 50%{transform:translateY(-7px) rotate(2deg)} }
  /* scientist avatar inside the badge */
  .hero-scientist { vertical-align:middle; margin-right:2px; }
  @media (max-width: 760px) { .hero-deco.c,.hero-deco.d,.hero-deco.e,.hero-deco.f,.hero-deco.g { display:none; } }

  /* ---- input ---- */
  .stTextArea textarea {
    background:#FFFFFF !important; border:1px solid #DEE2E6 !important; border-radius:10px !important;
    color:#1A202C !important; font-size:0.98rem !important; padding:0.9rem 1rem !important;
    box-shadow:0 1px 2px rgba(26,32,44,0.04) !important;
  }
  .stTextArea textarea:focus { border-color:#1098AD !important; box-shadow:0 0 0 4px rgba(16,152,173,0.12) !important; }
  .stButton > button {
    background:#1098AD !important; color:#fff !important; font-weight:700 !important; font-size:0.98rem !important;
    border:none !important; border-radius:10px !important; padding:0.7rem 1.9rem !important;
    box-shadow:0 6px 16px rgba(16,152,173,0.25) !important;
    transition: background 0.15s ease, transform 0.12s ease, box-shadow 0.15s ease !important;
  }
  .stButton > button:hover { background:#0C8599 !important; transform:translateY(-1px) !important; box-shadow:0 9px 22px rgba(16,152,173,0.34) !important; }

  /* ---- section dividers ---- */
  .sec {
    font-weight:700; font-size:0.74rem; color:#868E96; text-transform:uppercase;
    letter-spacing:0.12em; margin:1.7rem 0 0.7rem; display:flex; align-items:center; gap:0.55rem;
    font-family:'JetBrains Mono',monospace;
  }
  .sec::after { content:""; flex:1; height:1px; background:#E9ECEF; }

  /* ---- persona cards ---- */
  .pcard {
    background:#FFFFFF; border:1px solid #E9ECEF; border-left:4px solid;
    border-radius:8px; padding:1.05rem 1.2rem; margin-bottom:0.75rem;
    box-shadow:0 4px 14px rgba(26,32,44,0.05);
    animation: rise 0.45s cubic-bezier(0.22,1,0.36,1);
  }
  @keyframes rise { from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);} }
  .pcard-head { display:flex; align-items:center; gap:0.6rem; margin-bottom:0.5rem; }
  .pcard-emoji { width:38px; height:38px; border-radius:9px; display:grid; place-items:center; font-size:1.05rem; }
  .pcard-name { font-weight:700; font-size:0.97rem; color:#1A202C; }
  .pcard-sent { margin-left:auto; font-size:0.7rem; font-weight:700; padding:3px 10px; border-radius:6px; font-family:'JetBrains Mono',monospace; }
  .pcard-react { color:#343A40; font-size:0.92rem; line-height:1.6; }
  .pcard-obj { margin-top:0.7rem; padding-top:0.6rem; border-top:1px solid #F1F3F5; font-size:0.84rem; }
  .pcard-obj b { color:#1A202C; } .pcard-obj span { color:#495057; }

  .skel { background:#FFFFFF; border:1px dashed #DEE2E6; border-radius:8px; padding:1.05rem 1.2rem; margin-bottom:0.75rem; color:#ADB5BD; font-size:0.9rem; display:flex; align-items:center; gap:0.6rem; }
  .pulse { animation: blink 1.1s ease-in-out infinite; } @keyframes blink { 0%,100%{opacity:0.35;} 50%{opacity:1;} }

  /* ---- sentiment meter ---- */
  .meter { background:#FFFFFF; border:1px solid #E9ECEF; border-radius:10px; padding:1rem 1.15rem; box-shadow:0 4px 14px rgba(26,32,44,0.05); }
  .meter-h { font-weight:700; font-size:0.88rem; color:#1A202C; display:flex; align-items:center; justify-content:space-between; }
  .meter-h .count { font-family:'JetBrains Mono',monospace; font-size:0.76rem; color:#868E96; }
  .bar { display:flex; height:13px; border-radius:7px; overflow:hidden; margin-top:0.65rem; background:#F1F3F5; }
  .bar > div { transition:width 0.6s ease; }
  .legend { display:flex; gap:1.1rem; margin-top:0.65rem; font-size:0.78rem; color:#495057; font-family:'JetBrains Mono',monospace; }
  .legend span { display:flex; align-items:center; gap:0.35rem; }
  .sw { width:10px; height:10px; border-radius:3px; }

  /* ---- themes ---- */
  .tcard { background:#FFFFFF; border:1px solid #E9ECEF; border-left:4px solid #1098AD; border-radius:8px; padding:0.85rem 1.05rem; margin-bottom:0.6rem; box-shadow:0 3px 10px rgba(26,32,44,0.04); animation: rise 0.4s ease; }
  .tcard-name { font-weight:700; color:#1A202C; font-size:0.94rem; }
  .tcard-who { color:#868E96; font-size:0.77rem; margin-top:0.25rem; font-family:'JetBrains Mono',monospace; }
  .tcard-tension { color:#E8590C; font-size:0.85rem; margin-top:0.35rem; }
  .pill { border-radius:8px; padding:0.8rem 1.05rem; margin-top:0.5rem; }
  .pill-l { font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; font-family:'JetBrains Mono',monospace; }
  .pill-t { font-size:0.9rem; margin-top:0.2rem; color:#343A40; }

  /* ---- strategy ---- */
  .scard { background:#FFFFFF; border:1px solid #E9ECEF; border-radius:10px; padding:1.1rem 1.3rem; box-shadow:0 4px 14px rgba(26,32,44,0.06); }
  .sitem { display:flex; gap:0.7rem; padding:0.5rem 0; color:#343A40; font-size:0.92rem; line-height:1.55; }
  .sitem + .sitem { border-top:1px solid #F1F3F5; }
  .sitem .num { flex-shrink:0; width:22px; height:22px; border-radius:6px; background:#E7F5FF; color:#1098AD; font-size:0.72rem; font-weight:700; display:grid; place-items:center; font-family:'JetBrains Mono',monospace; }

  .demo { background:#FFF9DB; border:1px solid #FFE066; border-radius:10px; padding:0.6rem 1rem; color:#A8770A; font-size:0.85rem; margin-bottom:1rem; display:flex; align-items:center; gap:0.5rem; }
</style>
""", unsafe_allow_html=True)

# ---------- helpers ----------
def persona_card(r, i):
    c = color_for(i)
    s = SENTIMENT.get(r.get("sentiment", "mixed"), SENTIMENT["mixed"])
    return f"""
<div class="pcard" style="border-left-color:{c['border']};">
  <div class="pcard-head">
    <div class="pcard-emoji" style="background:{c['bg']};">{c['emoji']}</div>
    <div class="pcard-name">{r['persona']}</div>
    <div class="pcard-sent" style="background:{s['bg']}; color:{s['color']};">{s['dot']} {s['label']}</div>
  </div>
  <div class="pcard-react">{r['reaction']}</div>
  <div class="pcard-obj"><b>Holds them back:</b> <span>{r.get('key_objection','')}</span></div>
</div>"""

def skeleton(name):
    return f'<div class="skel"><span class="pulse">⚗️</span> {name} is reacting...</div>'

def theme_card(t):
    who = ", ".join(t.get("supported_by", []))
    tension = t.get("tension", "")
    th = f'<div class="tcard-tension">⚡ {tension}</div>' if tension else ""
    return f'<div class="tcard"><div class="tcard-name">{t["theme"]}</div><div class="tcard-who">Raised by: {who}</div>{th}</div>'

def sentiment_meter(reactions):
    counts = {"positive": 0, "mixed": 0, "negative": 0}
    for r in reactions:
        k = r.get("sentiment", "mixed"); counts[k] = counts.get(k, 0) + 1
    total = max(sum(counts.values()), 1)
    seg = "".join(f'<div style="width:{counts[k]/total*100}%; background:{SENTIMENT[k]["color"]};"></div>' for k in ["positive","mixed","negative"] if counts[k] > 0)
    legend = "".join(f'<span><i class="sw" style="background:{SENTIMENT[k]["color"]}"></i>{SENTIMENT[k]["label"]} {counts[k]}</span>' for k in ["positive","mixed","negative"])
    return f'<div class="meter"><div class="meter-h"><span>Panel sentiment</span><span class="count">n={total}</span></div><div class="bar">{seg}</div><div class="legend">{legend}</div></div>'

def strategy_card(strategy):
    lines = [ln.strip().lstrip("-*•▸ ").strip() for ln in strategy.replace(" - ", "\n- ").splitlines() if ln.strip().lstrip("-*•▸ ").strip()]
    items = "".join(f'<div class="sitem"><span class="num">{n+1:02d}</span><span>{ln}</span></div>' for n, ln in enumerate(lines))
    return f'<div class="scard">{items}</div>'

def render_moderation(mod):
    for t in mod.get("themes", []):
        st.markdown(theme_card(t), unsafe_allow_html=True)
    if mod.get("consensus"):
        st.markdown(f'<div class="pill" style="background:#E6FCF5; border:1px solid #B2F2DD;"><div class="pill-l" style="color:#0CA678;">✓ Consensus</div><div class="pill-t">{mod["consensus"]}</div></div>', unsafe_allow_html=True)
    if mod.get("biggest_risk"):
        st.markdown(f'<div class="pill" style="background:#FFF5F5; border:1px solid #FFC9C9;"><div class="pill-l" style="color:#FA5252;">⚠ Biggest risk</div><div class="pill-t">{mod["biggest_risk"]}</div></div>', unsafe_allow_html=True)

if "result" not in st.session_state:
    st.session_state.result = None

# ---------- sidebar (left-aligned metadata + accordions) ----------
with st.sidebar:
    st.markdown('<div class="side-title">🧪 Lab bench</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-sub">Controls & instrument routing</div>', unsafe_allow_html=True)
    demo_mode = st.toggle("Demo mode", value=False, help="Seeded example, no live API calls — safe for presentations.")
    with st.expander("Model routing", expanded=True):
        st.markdown('<div class="route-row">💸 Personas <span class="tag">Gemini Flash-Lite</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="route-row">🧭 Moderator <span class="tag">GPT-4o-mini</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="route-row">🧠 Strategist <span class="tag">Claude Haiku</span></div>', unsafe_allow_html=True)
    with st.expander("About this method", expanded=False):
        st.markdown("Persona Lab simulates a focus group of distinct AI personas. They react, a Moderator clusters the tensions, and a Strategist turns them into recommendations.")
    with st.expander("Cost", expanded=False):
        st.markdown('<div class="route-row">Estimated total <span class="tag">~$0–3</span></div>', unsafe_allow_html=True)

# ---------- hero ----------
st.markdown("""
<div class="hero">
  <!-- conical flask -->
  <svg class="hero-deco a" width="40" height="40" viewBox="0 0 48 48" fill="none"><path d="M19 6h10M21 6v13L13 38a4 4 0 0 0 4 5h14a4 4 0 0 0 4-5l-8-19V6" stroke="#1098AD" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 31h16" stroke="#0CA678" stroke-width="2" stroke-linecap="round"/><circle cx="22" cy="35" r="1.4" fill="#0CA678"/><circle cx="27" cy="38" r="1.2" fill="#F59F00"/></svg>
  <!-- molecule -->
  <svg class="hero-deco b" width="36" height="36" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="6" stroke="#7048E8" stroke-width="2"/><circle cx="10" cy="14" r="3" fill="#1098AD"/><circle cx="38" cy="16" r="3" fill="#0CA678"/><circle cx="12" cy="36" r="3" fill="#F59F00"/><path d="M15 16l5 5M33 18l-4 4M14 34l6-5" stroke="#CED4DA" stroke-width="1.6"/></svg>
  <!-- test tube -->
  <svg class="hero-deco c" width="26" height="26" viewBox="0 0 48 48" fill="none"><rect x="19" y="5" width="10" height="33" rx="5" stroke="#0CA678" stroke-width="2"/><path d="M19 25h10v8a5 5 0 0 1-10 0z" fill="#0CA678" fill-opacity="0.25"/><path d="M16 5h16" stroke="#1098AD" stroke-width="2" stroke-linecap="round"/></svg>
  <!-- microscope -->
  <svg class="hero-deco d" width="34" height="34" viewBox="0 0 48 48" fill="none"><path d="M22 10l6 3-7 14-6-3z" stroke="#1098AD" stroke-width="2" stroke-linejoin="round"/><path d="M18 26c-3 4-3 9 2 12h14" stroke="#7048E8" stroke-width="2" stroke-linecap="round"/><path d="M14 40h22" stroke="#343A40" stroke-width="2" stroke-linecap="round"/><circle cx="25" cy="11" r="2" fill="#F59F00"/></svg>
  <!-- beaker with bubbles -->
  <svg class="hero-deco e" width="30" height="30" viewBox="0 0 48 48" fill="none"><path d="M17 8h14v9l7 18a4 4 0 0 1-4 5H14a4 4 0 0 1-4-5l7-18z" stroke="#1098AD" stroke-width="2" stroke-linejoin="round"/><path d="M13 30h22" stroke="#0CA678" stroke-width="2"/><circle cx="22" cy="36" r="1.4" fill="#1098AD"/><circle cx="28" cy="33" r="1.2" fill="#F59F00"/><circle cx="25" cy="39" r="1" fill="#0CA678"/></svg>
  <!-- DNA helix -->
  <svg class="hero-deco f" width="28" height="28" viewBox="0 0 48 48" fill="none"><path d="M16 6c0 8 16 10 16 18s-16 10-16 18" stroke="#7048E8" stroke-width="2" stroke-linecap="round"/><path d="M32 6c0 8-16 10-16 18s16 10 16 18" stroke="#1098AD" stroke-width="2" stroke-linecap="round"/><path d="M18 12h12M17 18h14M17 30h14M18 36h12" stroke="#CED4DA" stroke-width="1.6"/></svg>
  <!-- bar chart -->
  <svg class="hero-deco g" width="26" height="26" viewBox="0 0 48 48" fill="none"><path d="M8 40h32" stroke="#343A40" stroke-width="2" stroke-linecap="round"/><rect x="12" y="26" width="6" height="14" rx="1.5" fill="#1098AD"/><rect x="21" y="18" width="6" height="22" rx="1.5" fill="#0CA678"/><rect x="30" y="12" width="6" height="28" rx="1.5" fill="#F59F00"/></svg>

  <div class="hero-badge">
    <svg class="hero-scientist" width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="6" r="3" stroke="#1098AD" stroke-width="1.8"/><path d="M6 22v-2a6 6 0 0 1 12 0v2" stroke="#1098AD" stroke-width="1.8" stroke-linecap="round"/><path d="M12 14v8M9.5 14.5l1 4M14.5 14.5l-1 4" stroke="#0CA678" stroke-width="1.6" stroke-linecap="round"/></svg>
    Synthetic Focus Group
  </div>
  <h1 class="hero-title"><span>Persona</span><span class="accent">Lab</span></h1>
  <div class="hero-sub">Drop in any idea. Watch five distinct personas react — and disagree.</div>
</div>
""", unsafe_allow_html=True)

DEMO_IDEA = "A subscription app that turns your grocery receipts into weekly meal plans."
idea_input = st.text_area("Your idea", placeholder="e.g. An app that scans your fridge and suggests recipes from what you already have...", height=100, label_visibility="collapsed")
col1, _ = st.columns([1, 3])
with col1:
    run_clicked = st.button("Run focus group  →", use_container_width=True)

if run_clicked:
    idea = DEMO_IDEA if demo_mode else idea_input.strip()
    if not idea:
        st.warning("Drop in an idea first.")
    else:
        st.session_state.result = None
        if demo_mode:
            st.markdown('<div class="demo">⚡ Demo mode — seeded example, no live API calls.</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec">🧑‍🔬 Panel reactions</div>', unsafe_allow_html=True)
        slots = [st.empty() for _ in PERSONAS]
        for i, p in enumerate(PERSONAS):
            slots[i].markdown(skeleton(p["name"]), unsafe_allow_html=True)
        reactions = [None] * len(PERSONAS)
        def run_one(idx_p):
            i, p = idx_p
            system = PERSONA_SYSTEM_TEMPLATE.format(name=p["name"], stance=p["stance"], priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea=idea)
            raw = call_llm("persona", system, idea, _mock_persona_for(p["name"]), idea)
            return i, _safe_json(raw, fallback={"persona": p["name"], "reaction": raw, "sentiment": "mixed", "key_objection": "n/a"})
        with ThreadPoolExecutor(max_workers=len(PERSONAS)) as ex:
            futures = {ex.submit(run_one, (i, p)): i for i, p in enumerate(PERSONAS)}
            for fut in concurrent.futures.as_completed(futures):
                i, r = fut.result()
                reactions[i] = r
                slots[i].markdown(persona_card(r, i), unsafe_allow_html=True)
        st.markdown('<div class="sec">📊 At a glance</div>', unsafe_allow_html=True)
        st.markdown(sentiment_meter(reactions), unsafe_allow_html=True)
        st.markdown('<div class="sec">🧭 Themes & tensions</div>', unsafe_allow_html=True)
        with st.spinner("Moderator clustering reactions..."):
            moderation = run_moderator(reactions)
        render_moderation(moderation)
        st.markdown('<div class="sec">🧠 Recommendations</div>', unsafe_allow_html=True)
        with st.spinner("Strategist synthesizing..."):
            strategy = run_strategist(moderation)
        st.markdown(strategy_card(strategy), unsafe_allow_html=True)
        st.session_state.result = {"idea": idea, "reactions": reactions, "moderation": moderation, "strategy": strategy}
elif st.session_state.result:
    out = st.session_state.result
    st.markdown('<div class="sec">🧑‍🔬 Panel reactions</div>', unsafe_allow_html=True)
    for i, r in enumerate(out["reactions"]):
        st.markdown(persona_card(r, i), unsafe_allow_html=True)
    st.markdown('<div class="sec">📊 At a glance</div>', unsafe_allow_html=True)
    st.markdown(sentiment_meter(out["reactions"]), unsafe_allow_html=True)
    st.markdown('<div class="sec">🧭 Themes & tensions</div>', unsafe_allow_html=True)
    render_moderation(out["moderation"])
    st.markdown('<div class="sec">🧠 Recommendations</div>', unsafe_allow_html=True)
    st.markdown(strategy_card(out["strategy"]), unsafe_allow_html=True)
