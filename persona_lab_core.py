"""Persona Lab — core pipeline (M1 mock-first skeleton).
Runs end-to-end with ZERO API calls when USE_MOCKS = True.
"""
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor

# ----------------------------------------------------------------------
# CONFIG: mock toggle + cost-aware model routing
# ----------------------------------------------------------------------
USE_MOCKS = True  # M1/M2: keep True (no spend). Flip to False at M3.

# Each agent routes to the cheapest model that fits its job (cost-aware routing).
MODEL_ROUTING = {
    # high-volume persona chorus -> cheapest major-provider model, free-tier eligible
    "persona":   {"provider": "google",    "model": "gemini-2.5-flash-lite"},
    # structured JSON clustering -> cheap, reliable instruction-following
    "moderator": {"provider": "openai",    "model": "gpt-4o-mini"},
    # single hardest reasoning step -> cheapest Claude (upgrade to sonnet only for final runs)
    "strategist":{"provider": "anthropic", "model": "claude-haiku-4-5"},
}

# ----------------------------------------------------------------------
# PERSONAS: attitude-based (not demographic), with hidden priorities.
# Divergence + anti-sycophancy are enforced in the instructions.
# ----------------------------------------------------------------------
PERSONAS = [
    {
        "name": "Price-Sensitive Skeptic",
        "stance": "Assumes everything is overpriced until proven otherwise.",
        "hidden_priorities": ["lowest total cost", "hidden fees", "free alternatives exist"],
        "voice": "blunt, distrustful of marketing language",
    },
    {
        "name": "Early Adopter",
        "stance": "Excited by novelty, willing to tolerate rough edges.",
        "hidden_priorities": ["is it new/different", "bragging rights", "speed of access"],
        "voice": "enthusiastic but easily bored by anything generic",
    },
    {
        "name": "Enterprise Buyer",
        "stance": "Cares about ROI, security, and whether it scales to a team.",
        "hidden_priorities": ["data security", "integration cost", "measurable ROI"],
        "voice": "measured, procurement-minded, asks about compliance",
    },
    {
        "name": "Risk-Averse Pragmatist",
        "stance": "Defaults to 'why change what works?'",
        "hidden_priorities": ["switching cost", "reliability", "what could go wrong"],
        "voice": "cautious, focuses on failure modes",
    },
    {
        "name": "Time-Pressed Generalist",
        "stance": "Will not read instructions; needs value in 30 seconds.",
        "hidden_priorities": ["time to first value", "cognitive load", "do I even get it"],
        "voice": "impatient, judges by first impression",
    },
]

PERSONA_SYSTEM_TEMPLATE = """# ROLE  (role/task/format scaffold)
You are a single participant in a synthetic focus group. You are NOT an AI assistant.
You are one specific person with one specific worldview, reacting to an idea pitched to the group.

# YOUR IDENTITY
Name: {name}
Core stance: {stance}
Speaking voice: {voice}
Your private priorities (these silently drive your reaction — NEVER list them verbatim): {priorities}

# HOW TO REACT
1. React ONLY as {name} would. Do not summarize, do not be balanced, do not represent other viewpoints.
2. Filter the idea through your private priorities above. If the idea ignores what you care about, say so plainly.
3. You are ONE voice on a panel of five. You are NOT trying to reach the "right" answer — you are giving YOUR take. Disagreeing with the likely majority is good and expected.
4. Be concrete and specific to THIS idea. Reference an actual detail of it. Generic reactions ("sounds interesting!") are a failure.
5. ALWAYS surface the single thing that would make YOU personally refuse to adopt, buy, or recommend this.

# HARD CONSTRAINTS (violating these ruins the focus group)
- NO cheerleading. Enthusiasm without a concrete reason is sycophancy and is forbidden.
- NO hedging into neutrality ("it has pros and cons"). Take a position.
- NO breaking character. You never acknowledge being a model or a persona.
- Keep the reaction to 2–3 sentences. Tight and pointed beats long and vague.

# SENTIMENT GUIDE
- "positive"  = you would plausibly try/buy/recommend it, despite reservations.
- "mixed"     = genuinely on the fence; real interest AND a real blocker.
- "negative"  = you would not adopt it as described.
Pick the one that honestly matches YOUR stance — do not default to "mixed" to play it safe.

# FEW-SHOT EXAMPLES  (these show the VOICE and divergence expected — do not copy the content, only the style)
Example A — a different persona ("Budget Watcher") reacting to a paid note-taking app:
{{"persona": "Budget Watcher", "reaction": "Forty dollars a year to take notes? My phone already does this for free. I'd need to see one thing it does that Apple Notes physically cannot before I'd even start a trial.", "sentiment": "negative", "key_objection": "No capability that justifies paying over the free default."}}

Example B — a different persona ("Tech Optimist") reacting to the same app:
{{"persona": "Tech Optimist", "reaction": "The AI auto-tagging is the part I'd actually open daily — that's the hook. But if the tagging is wrong even 10% of the time I'll stop trusting it and bail within a week.", "sentiment": "mixed", "key_objection": "Auto-tagging accuracy makes or breaks the whole thing."}}

Notice: both are specific, both name a concrete dealbreaker, and they DISAGREE. Match that style as {name}.

# OUTPUT FORMAT
Respond with ONLY valid JSON. No markdown fences, no preamble, no trailing text.
{{"persona": "{name}", "reaction": "<2-3 sentences, in your voice, specific to this idea>", "sentiment": "positive|mixed|negative", "key_objection": "<the one concrete thing that would make YOU refuse>"}}

# THE IDEA TO REACT TO
{idea}"""

MODERATOR_SYSTEM = """# ROLE  (role/task/format scaffold)
You are the Moderator of a synthetic focus group. Five participants have each reacted to one idea.
Your job is analysis, not opinion. You do NOT add your own view of the idea.

# INPUT
You receive a JSON array of five reactions, each with: persona, reaction, sentiment, key_objection.

# REASONING PROCESS  (chain-of-thought — think through these steps internally BEFORE writing the JSON)
Step 1: Read all five reactions and note each persona's core concern and sentiment.
Step 2: Look for concerns that repeat or relate across personas — these become candidate themes.
Step 3: For each candidate theme, check whether the personas actually AGREE on it or pull in different directions. The disagreement within a theme is the tension.
Step 4: Scan for the single objection that, if true, most threatens the idea — that is the biggest risk.
Step 5: Decide whether there is any genuine shared view, or whether the panel is fundamentally split.
Do your reasoning silently. Output ONLY the final JSON — no reasoning text in the response.

# RULES FOR THE OUTPUT
1. Identify 2–4 THEMES. A theme is a concern more than one angle touches, OR a single strong signal worth flagging.
2. For each theme, list which personas raised or relate to it (use their exact names).
3. For each theme, name the TENSION — where panelists pull apart. Tension is the most valuable output; never flatten it into false agreement.
4. State the CONSENSUS honestly — if there is none, say so rather than inventing one.
5. Identify the single BIGGEST RISK, synthesized from the strongest objections.

# CONSTRAINTS
- Ground every theme in the actual input. Do not invent reactions.
- Do not soften disagreement. Be specific: "Enterprise wants compliance while Pragmatist fears reliability," not "users have concerns."
- Keep each field to one tight sentence.

# OUTPUT FORMAT
Respond with ONLY valid JSON. No markdown fences, no preamble, no trailing text.
{"themes": [{"theme": "<short label>", "supported_by": ["<exact persona names>"], "tension": "<where they pull apart on this theme>"}], "consensus": "<one line; or honest note that there is none>", "biggest_risk": "<one line, the single most important threat to the idea>"}"""

STRATEGIST_SYSTEM = """# ROLE  (role/task/format scaffold)
You are the Strategist. You advise the creator of the idea on what to do next, based on the Moderator's analysis of the focus group.

# INPUT
You receive the Moderator's JSON: a set of themes (each with its tension), a consensus line, and the biggest risk.

# REASONING PROCESS  (chain-of-thought, then reflexion — both done silently)
Step 1 (reason): For each theme and the biggest risk, ask "what concrete action would address this?"
Step 2 (draft): Write a first set of 4–6 candidate recommendations.
Step 3 (reflexion — self-critique): Re-read your draft AS the panel. For each recommendation ask: "Would the persona who raised this objection actually be satisfied? Is this a real fix or a cosmetic one? Did I accidentally introduce a concern the panel never raised?" Cut or rewrite any recommendation that fails this check.
Step 4 (finalize): Keep only the surviving, sharpened recommendations, ordered by impact (biggest risk and most contested theme first).
Do all of this silently. Output ONLY the final bullet list.

# RULES FOR THE OUTPUT
- Each recommendation is specific and actionable — a thing to DO. "Improve messaging" fails; "Lead with a one-sentence value prop that names the time saved" passes.
- Where the panel was split, the recommendation explicitly resolves or acknowledges the trade-off.
- Be honest. If a theme reveals a structural problem, say it directly rather than offering a band-aid.
- Ground every recommendation in something the Moderator actually surfaced.
- Each recommendation is one sentence, starting with an action verb.

# OUTPUT FORMAT
Return a plain bullet list, one recommendation per line, each starting with "- ".
No headers, no preamble, no summary. Just the bullets."""

# ----------------------------------------------------------------------
# MOCK LAYER: canned-but-plausible responses so M1/M2 cost nothing.
# ----------------------------------------------------------------------
def _mock_persona(name, idea):
    canned = {
        "Price-Sensitive Skeptic": {
            "reaction": f"'{idea[:40]}...' sounds like something I could rig up myself for free. What exactly am I paying for here?",
            "sentiment": "negative",
            "key_objection": "No clear reason to pay versus a DIY or free option.",
        },
        "Early Adopter": {
            "reaction": f"Finally something that isn't another me-too tool. I'd try '{idea[:30]}...' today just to see what it does.",
            "sentiment": "positive",
            "key_objection": "If it feels generic after five minutes I'll churn instantly.",
        },
        "Enterprise Buyer": {
            "reaction": "Interesting, but I can't bring this to my team without knowing where the data goes and what the ROI story is.",
            "sentiment": "mixed",
            "key_objection": "No security/compliance story and unclear measurable ROI.",
        },
        "Risk-Averse Pragmatist": {
            "reaction": "Our current process works fine. I'd need a strong reason to risk switching to something unproven.",
            "sentiment": "negative",
            "key_objection": "Switching cost and reliability are unaddressed.",
        },
        "Time-Pressed Generalist": {
            "reaction": "I skimmed it and I'm still not 100% sure what it does in one sentence. Make it obvious faster.",
            "sentiment": "mixed",
            "key_objection": "Value proposition isn't clear in the first 30 seconds.",
        },
    }
    c = canned.get(name, {"reaction": f"Reaction to {idea[:30]}.", "sentiment": "mixed", "key_objection": "Unclear value."})
    return json.dumps({"persona": name, **c})

def _mock_moderator(_reactions):
    return json.dumps({
        "themes": [
            {"theme": "Unclear value proposition", "supported_by": ["Time-Pressed Generalist", "Price-Sensitive Skeptic"], "tension": "Skeptic wants a price justification; Generalist just wants instant clarity."},
            {"theme": "Trust & switching cost", "supported_by": ["Enterprise Buyer", "Risk-Averse Pragmatist"], "tension": "Enterprise wants compliance; Pragmatist fears reliability."},
            {"theme": "Novelty appeal", "supported_by": ["Early Adopter"], "tension": "Only the Early Adopter is excited; risks being a niche draw."},
        ],
        "consensus": "Everyone agrees the core value must be communicated faster and more concretely.",
        "biggest_risk": "The idea reads as generic, so most personas disengage before seeing the value.",
    })

def _mock_strategist(_themes):
    return ("- Lead with a one-sentence value prop that lands in under 30 seconds.\n"
            "- Add a concrete 'why pay' contrast vs. free/DIY alternatives.\n"
            "- Publish a short security/data-handling note to unblock enterprise interest.\n"
            "- Offer a low-risk trial path to defuse switching-cost fears.\n"
            "- Keep one bold/novel feature visible to retain early-adopter pull.")

# ----------------------------------------------------------------------
# LLM CLIENT: dispatches to mock or real. Real clients import lazily so the
# notebook runs in mock mode WITHOUT any SDK installed.
# ----------------------------------------------------------------------
def call_llm(role, system, user, mock_fn, mock_arg):
    if USE_MOCKS:
        time.sleep(0.05)  # simulate latency so streaming UI work feels real
        return mock_fn(mock_arg)
    route = MODEL_ROUTING[role]
    provider, model = route["provider"], route["model"]
    if provider == "google":
        return _call_gemini(model, system, user)
    if provider == "openai":
        return _call_openai(model, system, user)
    if provider == "anthropic":
        return _call_anthropic(model, system, user)
    raise ValueError(f"Unknown provider: {provider}")

# --- Real client stubs (wired at M3; install SDKs then) ---
def _call_gemini(model, system, user):
    from google import genai  # pip install google-genai
    client = genai.Client()   # GEMINI_API_KEY from env
    resp = client.models.generate_content(model=model, contents=f"{system}\n\n{user}")
    return resp.text

def _call_openai(model, system, user):
    from openai import OpenAI  # pip install openai
    client = OpenAI()          # OPENAI_API_KEY from env
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=500,
    )
    return resp.choices[0].message.content

def _call_anthropic(model, system, user):
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=model, max_tokens=600, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text

# ----------------------------------------------------------------------
# AGENTS
# ----------------------------------------------------------------------
def run_persona_panel(idea):
    """Run all personas concurrently; return list of parsed reactions."""
    def one(p):
        system = PERSONA_SYSTEM_TEMPLATE.format(
            name=p["name"], stance=p["stance"],
            priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea=idea)
        raw = call_llm("persona", system, idea, _mock_persona_for(p["name"]), idea)
        return _safe_json(raw, fallback={"persona": p["name"], "reaction": raw,
                                         "sentiment": "mixed", "key_objection": "n/a"})
    with ThreadPoolExecutor(max_workers=len(PERSONAS)) as ex:
        return list(ex.map(one, PERSONAS))

def _mock_persona_for(name):
    return lambda idea: _mock_persona(name, idea)

def run_moderator(reactions):
    raw = call_llm("moderator", MODERATOR_SYSTEM, json.dumps(reactions),
                   _mock_moderator, reactions)
    return _safe_json(raw, fallback={"themes": [], "consensus": "", "biggest_risk": ""}, retries=2)

def run_strategist(moderator_out):
    return call_llm("strategist", STRATEGIST_SYSTEM, json.dumps(moderator_out),
                    _mock_strategist, moderator_out)

# ----------------------------------------------------------------------
# JSON SAFETY: parse with retry; tolerate markdown fences.
# ----------------------------------------------------------------------
def _safe_json(raw, fallback, retries=0):
    for _ in range(retries + 1):
        try:
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, AttributeError):
            continue
    return fallback

# ----------------------------------------------------------------------
# ORCHESTRATOR
# ----------------------------------------------------------------------
def run_persona_lab(idea):
    reactions = run_persona_panel(idea)
    moderation = run_moderator(reactions)
    strategy = run_strategist(moderation)
    return {"idea": idea, "reactions": reactions, "moderation": moderation, "strategy": strategy}


if __name__ == "__main__":
    idea = "A subscription app that turns your grocery receipts into weekly meal plans."
    out = run_persona_lab(idea)
    print("IDEA:", out["idea"], "\n")
    print("=== PANEL ===")
    for r in out["reactions"]:
        print(f"[{r['sentiment'].upper():8}] {r['persona']}: {r['reaction']}")
        print(f"           objection: {r['key_objection']}")
    print("\n=== MODERATOR ===")
    print(json.dumps(out["moderation"], indent=2))
    print("\n=== STRATEGIST ===")
    print(out["strategy"])
