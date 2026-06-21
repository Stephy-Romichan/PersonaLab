"""
Persona Lab — Streamlit UI ("Light Lab", playful edition)
Animated talking SVG faces, game-style colors, per-persona personality,
and a personality side panel. Backend contract & call paths unchanged
(degrade chain, cache warming, mock toggle all preserved).
"""

import concurrent.futures
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

from persona_lab_core import (
    run_persona_panel, run_moderator, run_strategist, PERSONAS,
    call_llm, PERSONA_SYSTEM_TEMPLATE, _mock_persona_for, _safe_json,
    _call_persona_with_degrade, USE_MOCKS, warm_persona_caches,
)

st.set_page_config(page_title="Persona Lab", page_icon="🧪", layout="wide",
                   initial_sidebar_state="expanded")

# ---- persona personality presentation (keyed by name; falls back by index) ----
# face: a builder key controlling the SVG expression; tone: chip color family
PERSONA_UI = {
    "Price-Sensitive Skeptic": {"emoji":"💸","face":"skeptic","accent":"#FA5252","bg":"#FFF0F1",
        "tagline":"\"Prove it's worth my money.\"",
        "blurb":"Tightfisted and unconvinced. Wants the cheapest path and assumes there's a free alternative."},
    "Early Adopter": {"emoji":"🚀","face":"happy","accent":"#F59F00","bg":"#FFF8E1",
        "tagline":"\"Ooh, shiny — let me try it!\"",
        "blurb":"Loves novelty and bragging rights. Forgives rough edges, but bores fast if it feels generic."},
    "Enterprise Buyer": {"emoji":"🏢","face":"glasses","accent":"#0CA678","bg":"#E7FBF3",
        "tagline":"\"What's the ROI and is it secure?\"",
        "blurb":"Measured and procurement-minded. Thinks in teams, budgets, security and compliance."},
    "Risk-Averse Pragmatist": {"emoji":"🛡️","face":"worried","accent":"#4263EB","bg":"#EDF1FF",
        "tagline":"\"…but what could go wrong?\"",
        "blurb":"Cautious by default. Fixated on switching cost, reliability, and failure modes."},
    "Time-Pressed Generalist": {"emoji":"⏱️","face":"flat","accent":"#7048E8","bg":"#F3EFFF",
        "tagline":"\"Make it obvious in 30 seconds.\"",
        "blurb":"Impatient and skimming. Judges instantly; needs value before it has to think."},
}
FALLBACK_UI = [
    {"emoji":"🧩","face":"flat","accent":"#E64980","bg":"#FFF0F6","tagline":"","blurb":"A tailored panelist for this idea."},
    {"emoji":"🔬","face":"happy","accent":"#1098AD","bg":"#E7F9FB","tagline":"","blurb":"A tailored panelist for this idea."},
]
def ui_for(name, i):
    return PERSONA_UI.get(name, FALLBACK_UI[i % len(FALLBACK_UI)])

SENTIMENT = {
    "positive": {"label":"Positive","color":"#0CA678","bg":"#E6FCF5","face":"happy"},
    "mixed":    {"label":"Mixed","color":"#F59F00","bg":"#FFF9DB","face":"flat"},
    "negative": {"label":"Negative","color":"#FA5252","bg":"#FFF5F5","face":"skeptic"},
}

# ---- SVG face builder: returns an inline svg for a given expression + color ----
def face_svg(expr, accent, bg, talking=False, size=58):
    eyes = {
        "happy":   f'<path d="M22 31c2-2.6 6.5-2.6 8.5 0" fill="none" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/><path d="M43.5 31c2-2.6 6.5-2.6 8.5 0" fill="none" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
        "skeptic": f'<circle cx="27" cy="33" r="3" fill="{accent}"/><circle cx="47" cy="33" r="3" fill="{accent}"/><path d="M20 25l9 3M54 25l-9 3" stroke="{accent}" stroke-width="2.3" stroke-linecap="round"/>',
        "worried": f'<circle cx="27" cy="34" r="2.8" fill="{accent}"/><circle cx="47" cy="34" r="2.8" fill="{accent}"/><path d="M19 27l9 2M55 27l-9 2" stroke="{accent}" stroke-width="2.2" stroke-linecap="round"/>',
        "glasses": f'<rect x="20" y="29" width="14" height="9" rx="2.5" fill="none" stroke="{accent}" stroke-width="2"/><rect x="40" y="29" width="14" height="9" rx="2.5" fill="none" stroke="{accent}" stroke-width="2"/><path d="M34 33h6" stroke="{accent}" stroke-width="2"/>',
        "flat":    f'<circle cx="27" cy="33" r="3" fill="{accent}"/><circle cx="47" cy="33" r="3" fill="{accent}"/>',
    }.get(expr, f'<circle cx="27" cy="33" r="3" fill="{accent}"/><circle cx="47" cy="33" r="3" fill="{accent}"/>')
    if talking:
        mouth = f'<ellipse class="mouth-talk" cx="37" cy="49" rx="6" ry="5" fill="{accent}" style="transform-origin:37px 49px"/>'
    else:
        mouth = {
            "happy":   f'<path d="M26 47c5 6 17 6 22 0" fill="none" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
            "skeptic": f'<path d="M26 50c5-5 17-5 22 0" fill="none" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
            "worried": f'<path d="M28 49h18" fill="none" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
            "glasses": f'<path d="M29 49h16" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
            "flat":    f'<path d="M28 49h18" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>',
        }.get(expr, f'<path d="M28 49h18" stroke="{accent}" stroke-width="2.6" stroke-linecap="round"/>')
    blink = '<g class="blink">' + eyes + '</g>'
    cls = "face-bob" + (" face-talk-wrap" if talking else "")
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 74 74" style="overflow:visible">'
            f'<circle cx="37" cy="37" r="32" fill="{bg}" stroke="{accent}" stroke-width="1.4"/>'
            f'{blink}{mouth}</svg>')

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
  .stApp {
    background:
      radial-gradient(1100px 460px at 80% -10%, rgba(240,159,0,0.08), transparent 60%),
      radial-gradient(900px 420px at 8% 0%, rgba(12,166,120,0.08), transparent 55%),
      radial-gradient(700px 360px at 50% 110%, rgba(66,99,235,0.06), transparent 60%),
      #FBFAF7;
    color:#1A202C; font-family:'Inter',sans-serif;
  }
  #MainMenu, footer, header { visibility:hidden; }
  .block-container { padding-top:1.5rem; padding-bottom:3rem; max-width:900px; }

  @media (prefers-reduced-motion: no-preference){
    .face-bob{animation:bob 3.2s ease-in-out infinite}
    .blink{animation:blink 4.2s ease-in-out infinite;transform-origin:center}
    .mouth-talk{animation:talk .42s ease-in-out infinite}
    .pcard{animation:pop .5s cubic-bezier(.22,1,.36,1)}
    .chip-face .face-bob{animation:bob 2.6s ease-in-out infinite}
  }
  @keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
  @keyframes blink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
  @keyframes talk{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
  @keyframes pop{from{opacity:0;transform:scale(.9) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}
  .dots span{display:inline-block;animation:d 1.4s infinite}
  .dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
  @keyframes d{0%,100%{opacity:.3}50%{opacity:1}}

  .hero{position:relative;text-align:center;padding:1.4rem 0 0.4rem;}
  .hero-badge{display:inline-flex;align-items:center;gap:6px;background:#FFF3D6;color:#9A5B00;font-family:'JetBrains Mono',monospace;font-size:0.7rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:5px 13px;border-radius:20px;border:1.5px solid #FFE08A;}
  .hero-title{font-family:'Baloo 2',cursive;font-size:3.4rem;font-weight:700;color:#1A202C;margin:0.5rem 0 0;line-height:1.0;display:flex;align-items:baseline;justify-content:center;gap:0.6rem;}
  .hero-title .accent{color:#0CA678;}
  .hero-sub{color:#5A6270;font-size:1.05rem;margin-top:0.4rem;}

  .stTextArea textarea{background:#FFFFFF !important;border:2px solid #E9E4D8 !important;border-radius:14px !important;color:#1A202C !important;font-size:0.98rem !important;padding:0.9rem 1rem !important;}
  .stTextArea textarea:focus{border-color:#0CA678 !important;box-shadow:0 0 0 4px rgba(12,166,120,0.14) !important;}
  .stButton > button{background:#0CA678 !important;color:#fff !important;font-family:'Baloo 2',cursive !important;font-weight:600 !important;font-size:1.02rem !important;border:none !important;border-radius:13px !important;padding:0.6rem 2rem !important;box-shadow:0 5px 0 #0B8A63 !important;transition:transform 0.08s ease, box-shadow 0.08s ease !important;}
  .stButton > button:hover{transform:translateY(2px) !important;box-shadow:0 3px 0 #0B8A63 !important;}

  .sec{font-family:'Baloo 2',cursive;font-weight:600;font-size:1rem;color:#3A4150;margin:1.7rem 0 0.7rem;display:flex;align-items:center;gap:0.5rem;}
  .sec::after{content:"";flex:1;height:2px;border-radius:2px;background:#EFE9DC;}

  .pcard{background:#FFFFFF;border:2px solid;border-radius:18px;padding:1rem 1.15rem;margin-bottom:0.85rem;box-shadow:0 5px 0 rgba(26,32,44,0.05);}
  .pcard-row{display:flex;align-items:flex-start;gap:13px;}
  .pcard-facecol{display:flex;flex-direction:column;align-items:center;gap:5px;flex-shrink:0;width:64px;}
  .pcard-badge{font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;padding:2px 8px;border-radius:20px;white-space:nowrap;}
  .bubble{position:relative;background:#FBFAF7;border:1.5px solid #ECE6D8;border-radius:14px;padding:0.65rem 0.9rem;}
  .bubble::before{content:"";position:absolute;left:-8px;top:16px;width:0;height:0;border-top:7px solid transparent;border-bottom:7px solid transparent;border-right:9px solid #ECE6D8;}
  .bubble::after{content:"";position:absolute;left:-6px;top:17px;width:0;height:0;border-top:6px solid transparent;border-bottom:6px solid transparent;border-right:7px solid #FBFAF7;}
  .bubble-txt{font-size:13.5px;line-height:1.55;color:#2A2F3A;}
  .pcard-name{font-family:'Baloo 2',cursive;font-weight:600;font-size:1rem;margin-top:7px;color:#1A202C;}
  .pcard-obj{margin-top:4px;font-size:12px;color:#6A717E;}
  .pcard-obj b{color:#1A202C;}

  .skel{background:#FFFFFF;border:2px dashed #E5DFD0;border-radius:18px;padding:1rem 1.15rem;margin-bottom:0.85rem;}
  .skel-row{display:flex;align-items:center;gap:13px;}
  .skel-txt{color:#9AA0AC;font-size:0.92rem;}

  .meter{background:#FFFFFF;border:2px solid #EFE9DC;border-radius:16px;padding:1rem 1.15rem;box-shadow:0 5px 0 rgba(26,32,44,0.04);}
  .meter-h{font-family:'Baloo 2',cursive;font-weight:600;font-size:0.95rem;color:#1A202C;display:flex;justify-content:space-between;align-items:center;}
  .meter-h .count{font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:#9AA0AC;}
  .bar{display:flex;height:15px;border-radius:10px;overflow:hidden;margin-top:0.6rem;background:#F1ECE0;}
  .bar>div{transition:width 0.6s ease;}
  .legend{display:flex;gap:1.1rem;margin-top:0.6rem;font-size:0.78rem;color:#5A6270;font-family:'JetBrains Mono',monospace;}
  .legend span{display:flex;align-items:center;gap:0.35rem;}
  .sw{width:10px;height:10px;border-radius:4px;}

  .tcard{background:#FFFFFF;border:2px solid #EFE9DC;border-radius:14px;padding:0.8rem 1rem;margin-bottom:0.6rem;box-shadow:0 4px 0 rgba(26,32,44,0.04);}
  .tcard-name{font-family:'Baloo 2',cursive;font-weight:600;color:#1A202C;font-size:0.96rem;}
  .tcard-who{color:#9AA0AC;font-size:0.77rem;margin-top:0.25rem;font-family:'JetBrains Mono',monospace;}
  .tcard-tension{color:#E8590C;font-size:0.85rem;margin-top:0.35rem;}
  .pill{border-radius:14px;padding:0.75rem 1rem;margin-top:0.5rem;}
  .pill-l{font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;font-family:'JetBrains Mono',monospace;}
  .pill-t{font-size:0.9rem;margin-top:0.2rem;color:#2A2F3A;}

  .scard{background:#FFFFFF;border:2px solid #DDF3EA;border-radius:16px;padding:1rem 1.25rem;box-shadow:0 5px 0 rgba(12,166,120,0.08);}
  .sitem{display:flex;gap:0.7rem;padding:0.5rem 0;color:#2A2F3A;font-size:0.92rem;line-height:1.55;}
  .sitem + .sitem{border-top:1.5px solid #F0ECE0;}
  .sitem .num{flex-shrink:0;width:24px;height:24px;border-radius:8px;background:#E6FCF5;color:#0B8A63;font-size:0.72rem;font-weight:700;display:grid;place-items:center;font-family:'JetBrains Mono',monospace;}

  /* sidebar persona cards */
  .roster-card{background:#fff;border:2px solid;border-radius:14px;padding:0.6rem 0.7rem;margin-bottom:0.55rem;}
  .roster-top{display:flex;align-items:center;gap:9px;}
  .roster-name{font-family:'Baloo 2',cursive;font-weight:600;font-size:0.86rem;color:#1A202C;line-height:1.1;}
  .roster-tag{font-size:0.74rem;color:#6A717E;font-style:italic;margin-top:1px;}
  .roster-blurb{font-size:0.74rem;color:#5A6270;margin-top:0.4rem;line-height:1.4;}
  .demo{background:#FFF9DB;border:2px solid #FFE066;border-radius:13px;padding:0.6rem 1rem;color:#9A5B00;font-size:0.85rem;margin-bottom:1rem;}
</style>
""", unsafe_allow_html=True)

def persona_card(r, i):
    name = r.get("persona", f"Persona {i+1}")
    ui = ui_for(name, i)
    s = SENTIMENT.get(r.get("sentiment", "mixed"), SENTIMENT["mixed"])
    face = face_svg(s["face"], ui["accent"], ui["bg"], talking=False)
    return f"""
<div class="pcard" style="border-color:{ui['accent']};">
  <div class="pcard-row">
    <div class="pcard-facecol">
      {face}
      <div class="pcard-badge" style="background:{s['bg']};color:{s['color']};">{s['label']}</div>
    </div>
    <div style="flex:1;">
      <div class="bubble"><div class="bubble-txt">{r['reaction']}</div></div>
      <div class="pcard-name">{ui['emoji']} {name}</div>
      <div class="pcard-obj"><b>Holds them back:</b> {r.get('key_objection','')}</div>
    </div>
  </div>
</div>"""

def skeleton(name, i):
    ui = ui_for(name, i)
    face = face_svg(ui["face"], ui["accent"], ui["bg"], talking=True)
    return f"""
<div class="skel">
  <div class="skel-row">
    <div class="pcard-facecol">{face}</div>
    <div class="skel-txt">{ui['emoji']} <b>{name}</b> is reacting<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
  </div>
</div>"""

def theme_card(t):
    who = ", ".join(t.get("supported_by", []))
    tension = t.get("tension", "")
    th = f'<div class="tcard-tension">⚡ {tension}</div>' if tension else ""
    return f'<div class="tcard"><div class="tcard-name">{t["theme"]}</div><div class="tcard-who">Raised by: {who}</div>{th}</div>'

def sentiment_meter(reactions):
    counts = {"positive":0,"mixed":0,"negative":0}
    for r in reactions:
        k = r.get("sentiment","mixed"); counts[k] = counts.get(k,0)+1
    total = max(sum(counts.values()),1)
    colors = {"positive":"#0CA678","mixed":"#F59F00","negative":"#FA5252"}
    seg = "".join(f'<div style="width:{counts[k]/total*100}%;background:{colors[k]};"></div>' for k in ["positive","mixed","negative"] if counts[k]>0)
    legend = "".join(f'<span><i class="sw" style="background:{colors[k]}"></i>{SENTIMENT[k]["label"]} {counts[k]}</span>' for k in ["positive","mixed","negative"])
    return f'<div class="meter"><div class="meter-h"><span>Panel sentiment</span><span class="count">n={total}</span></div><div class="bar">{seg}</div><div class="legend">{legend}</div></div>'

def strategy_card(strategy):
    lines = [ln.strip().lstrip("-*•▸ ").strip() for ln in strategy.replace(" - ","\n- ").splitlines() if ln.strip().lstrip("-*•▸ ").strip()]
    items = "".join(f'<div class="sitem"><span class="num">{n+1:02d}</span><span>{ln}</span></div>' for n,ln in enumerate(lines))
    return f'<div class="scard">{items}</div>'

def render_moderation(mod):
    for t in mod.get("themes", []):
        st.markdown(theme_card(t), unsafe_allow_html=True)
    if mod.get("consensus"):
        st.markdown(f'<div class="pill" style="background:#E6FCF5;border:2px solid #B2F2DD;"><div class="pill-l" style="color:#0B8A63;">✓ Consensus</div><div class="pill-t">{mod["consensus"]}</div></div>', unsafe_allow_html=True)
    if mod.get("biggest_risk"):
        st.markdown(f'<div class="pill" style="background:#FFF5F5;border:2px solid #FFC9C9;"><div class="pill-l" style="color:#D43A3A;">⚠ Biggest risk</div><div class="pill-t">{mod["biggest_risk"]}</div></div>', unsafe_allow_html=True)

if "result" not in st.session_state:
    st.session_state.result = None

# ---- sidebar: meet the panel ----
with st.sidebar:
    st.markdown('<div style="font-family:Baloo 2,cursive;font-weight:700;font-size:1.15rem;">🧪 Meet the panel</div>', unsafe_allow_html=True)
    st.caption("Five personalities, five points of view.")
    for i, p in enumerate(PERSONAS):
        ui = ui_for(p["name"], i)
        face = face_svg(ui["face"], ui["accent"], ui["bg"], talking=False, size=40)
        st.markdown(f"""
<div class="roster-card chip-face" style="border-color:{ui['accent']};">
  <div class="roster-top">{face}
    <div><div class="roster-name">{ui['emoji']} {p['name']}</div>
    <div class="roster-tag">{ui['tagline']}</div></div>
  </div>
  <div class="roster-blurb">{ui['blurb']}</div>
</div>""", unsafe_allow_html=True)
    st.markdown("---")
    demo_mode = st.toggle("Demo mode", value=False, help="Seeded example, no live API calls.")
    with st.expander("Model routing", expanded=False):
        st.markdown("💸 Personas · `Gemini Flash-Lite`")
        st.markdown("🧭 Moderator · `GPT-4o-mini`")
        st.markdown("🧠 Strategist · `Claude Haiku`")
    st.caption("Cost-aware routing · ~$0–3 total")

# ---- hero ----
st.markdown("""
<div class="hero">
  <div class="hero-badge">🧪 Synthetic Focus Group</div>
  <h1 class="hero-title"><span>Persona</span><span class="accent">Lab</span></h1>
  <div class="hero-sub">Drop in any idea. Watch five personalities react — and disagree.</div>
</div>
""", unsafe_allow_html=True)

DEMO_IDEA = "A subscription app that turns your grocery receipts into weekly meal plans."
idea_input = st.text_area("Your idea", placeholder="e.g. A monthly box that delivers a surprise hobby kit — pottery, calligraphy, beekeeping...", height=100, label_visibility="collapsed")
col1, _ = st.columns([1, 3])
with col1:
    run_clicked = st.button("Run focus group  →", use_container_width=True)

if run_clicked:
    idea = DEMO_IDEA if demo_mode else idea_input.strip()
    if not idea:
        st.warning("Drop in an idea first!")
    else:
        st.session_state.result = None
        if demo_mode:
            st.markdown('<div class="demo">⚡ Demo mode — seeded example, no live API calls.</div>', unsafe_allow_html=True)
        if not USE_MOCKS:
            try:
                warm_persona_caches()
            except Exception:
                pass
        st.markdown('<div class="sec">🧑‍🔬 Panel reactions</div>', unsafe_allow_html=True)
        slots = [st.empty() for _ in PERSONAS]
        for i, p in enumerate(PERSONAS):
            slots[i].markdown(skeleton(p["name"], i), unsafe_allow_html=True)
        reactions = [None] * len(PERSONAS)
        def run_one(idx_p):
            i, p = idx_p
            system = PERSONA_SYSTEM_TEMPLATE.format(name=p["name"], stance=p["stance"], priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea=idea)
            if USE_MOCKS:
                raw = _mock_persona_for(p["name"])(idea)
            else:
                raw = _call_persona_with_degrade(system, idea, p["name"])
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
