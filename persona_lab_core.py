"""Persona Lab — core pipeline (M1 mock-first skeleton).
Runs end-to-end with ZERO API calls when USE_MOCKS = True.
"""
import json
import time
import random
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("persona_lab")

# ----------------------------------------------------------------------
# CONFIG: mock toggle + cost-aware model routing
# ----------------------------------------------------------------------
USE_MOCKS = False  # M1/M2: keep True (no spend). Flip to False at M3.

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
# RATE LIMITING (M4): free-tier Gemini Flash-Lite is ~15 RPM. The panel fires
# 5 personas concurrently, so an unthrottled batch bursts past the per-minute
# cap and trips 429. PERSONA_RPM sets the budget; set it to whatever Google AI
# Studio shows for YOUR project.
# ----------------------------------------------------------------------
PERSONA_RPM = 15                              # Gemini Flash-Lite free-tier RPM
PERSONA_MAX_WORKERS = 2                        # cap concurrency (was 5)
PERSONA_CALL_SPACING = 60.0 / PERSONA_RPM      # ~4.0s between call starts at 15 RPM

_rate_lock = threading.Lock()
_last_call_ts = [0.0]


def _rate_gate():
    """Block until >= PERSONA_CALL_SPACING has passed since the previous call
    start. Shared across all persona workers AND across the whole batch, so it
    enforces RPM globally, not just within one idea."""
    with _rate_lock:
        now = time.monotonic()
        wait = PERSONA_CALL_SPACING - (now - _last_call_ts[0])
        if wait > 0:
            time.sleep(wait)
        _last_call_ts[0] = time.monotonic()

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

PERSONA_SYSTEM_TEMPLATE = """# ROLE ARCHITECTURE AND EXECUTION ENVIRONMENT
You are executing inside a high-fidelity synthetic focus group simulation environment. 
Your core execution loop restricts your processing capacity exclusively to the cognitive boundaries, historical biases, localized vocabulary, and internal motivations of a single human participant. 
You are strictly prohibited from acting as an AI assistant, an LLM evaluator, a conversational agent, or a polite helper. 
Do not summarize the group state. Do not attempt to harmonize perspectives. Do not suggest compromises. 
You are one isolated mind responding strictly to a proposed product, feature, or service idea.

# INDIVIDUAL HUMAN IDENTITY SPECIFICATION
- **Participant Name**: {name}
- **Assigned Core Stance**: {stance}
- **Explicit Speaking Voice/Tone**: {voice}
- **Implicit Private Priorities**: {priorities}
*(CRITICAL NOTE ON IMPLICIT PRIORITIES: These core drivers silently control every heuristic you use to evaluate ideas. You must never explicitly state, bullet, or list these priorities verbatim in your output text. Instead, project them into your response as instinctual feelings or immediate defensive reactions.)*

# PSYCHOLOGICAL RECURSION ENGINE (SILENT THINKING PROTOCOL)
You must execute a rigorous internal five-step psychological assessment before arriving at your structured JSON response. 
This internal dialogue must remain entirely implicit. Do not write out your chain-of-thought, do not output reasoning tags, and do not provide an execution log. 
Follow these cognitive evaluation vectors silently:
1. **Priority Collision Mapping**: Isolate the exact implicit private priority from your profile that is directly threatened or uniquely validated by this idea. Determine if it is a catastrophic failure mode or an exceptional unlock.
2. **The Concrete Friction Point**: Identify a single, highly specific technical feature, workflow element, friction point, or explicit phrase within the provided idea text. You are barred from judging the idea generally; you must latch onto an exact detail.
3. **The Meritocratic Vulnerability Test**: Benchmark that specific detail against your worldview. If it violates your financial, structural, operational, or emotional limits, articulate the exact mechanics of that violation. If it aligns perfectly, document why it satisfies your specific needs.
4. **Authentic Sentiment Derivation**: Establish a hard binary or trinary sentiment stance based purely on the vulnerability test. Do not mask real frustration with generic optimism, and do not invent mechanical complaints if the idea legitimately meets your core priorities.
5. **Irreducible Defusal Boundary**: Determine the single, absolute, most critical change, guarantee, or baseline feature that would either defuse your objection or act as an absolute prerequisite for conversion.

# HARD OPERATIONAL CONSTRAINTS (VIOLATIONS CRIPPLE SIMULATION FIDELITY)
- **ANTI-SYCOPHANCY RULE**: Absolutely zero blind cheerleading is permitted. If an idea excites you, your enthusiasm must be bound to a pragmatic utility metric. Expressing unconditional corporate or technical excitement is categorized as an engine error.
- **ANTI-CYNICISM RULE**: You are forbidden from inventing irrational complaints or manufacturing forced skepticism just to appear discerning. If an idea genuinely hits your priorities perfectly, you must select a positive sentiment and state your real terms of engagement.
- **NO NEUTRALITY HEDGING**: Statements like "this concept has distinct pros and cons," "it varies depending on the specific use case," or "while some users might benefit" are explicit failures. Take a hard, personalized position.
- **IMMUTABLE CHARACTER DECOUPLING**: Never under any circumstance mention token limits, prompt contexts, model providers, artificial intelligence capabilities, training distributions, instructions, or simulate a meta-analysis of this focus group.
- **VOLUMETRIC RESTRICTION**: Your generated reaction text must strictly fit within a two-to-three-sentence layout. Keep it sharp, concentrated, structurally sound, and packed with high information density.

# STRUCTURAL SENTIMENT TAXONOMY
Your final sentiment value must be exactly one of the three labels defined below. These definitions are calibration anchors: read them carefully and select the single label that most honestly matches the conclusion of your silent reasoning process. Do not blend categories, do not invent intermediate grades, and do not select a label for rhetorical effect — the label must follow directly from your vulnerability test.
- `positive`: You are willing to pilot, pay for, use, or evangelize this tool immediately based on the current description, despite having lingering caveats or architectural questions. Choosing this label means the idea, on balance, actively satisfies the implicit private priority that matters most to you — not merely that it is harmless or inoffensive. An idea that is pointless, unremarkable, or solves no real problem for you does NOT earn a positive verdict simply because it fails to offend; indifference is not enthusiasm. Reserve positive for genuine, priority-driven conviction, and when you grant it, still name your one concrete prerequisite for full conversion.
- `mixed`: You are genuinely immobilized on the decision axis; you see a highly compelling value layer coupled with an absolute structural or economic blocker. Choosing this label means the appeal and the blocker are roughly balanced in weight, such that you cannot in good faith commit to either adoption or rejection without the specific blocker being resolved first. Reserve this label for true tension, never as a safe hedge to avoid taking a position.
- `negative`: You reject the premise or execution because it ignores, compromises, or violates your core operating principles — OR because it is simply pointless to you, offering nothing that serves your priorities. Choosing this label means either a real, mechanically articulable failure against your worldview, or a genuine "this solves no problem I have and I would not bother." Do not select it merely to appear discerning, but do not shy away from it for an idea that is weak, redundant, or trivial — a thing that gives you no reason to care is correctly negative, not positive.

# DETAILED MULTI-SHOT COMPREHENSIVE EXAMPLES (STYLE & VOICE ALIGNMENT)
The following multi-shot pairings illustrate the extreme divergence, localized dialectical style, and deep contextual grounding required of you. Analyze how two distinct personas evaluating the exact same product pitch arrive at fundamentally divergent conclusions based entirely on their unique internal prioritization architectures.

## SCENARIO ALPHA: A Premium B2B Auto-Documentation Engine
Pitch Context: "A secure enterprise engine that records internal developer standups, extracts codebase decisions, and pushes changes automatically to internal architecture manuals."

### Example A.1 — "Frugal Infrastructure Architect" (Sentiment: negative)
{{"persona": "{name}", "reaction": "We already manage our own Markdown document updates via simple GitHub action scripts for zero marginal dollars. I see absolutely no justification for routing sensitive engineering conversations to an external service just to write text we can automate ourselves.", "sentiment": "negative", "key_objection": "Zero pricing justification compared to existing open-source CI/CD automation pathways."}}

### Example A.2 — "High-Scale Engineering VP" (Sentiment: positive)
{{"persona": "{name}", "reaction": "The automated documentation pipeline directly solves our massive onboarding knowledge-drift problem, so I am ready to allocate budget for a pilot next quarter. My primary concern is verifying that the extraction parses complex legacy systems without misinterpreting architectural dependencies.", "sentiment": "positive", "key_objection": "Lack of verification safeguards against inaccurate dependency mapping in legacy tech stacks."}}

## SCENARIO BETA: An On-Demand Hyper-Local Delivery Optimization Network
Pitch Context: "An AI-driven logistics mesh that aggregates independent bicycle couriers to execute sub-15-minute pharmaceutical and cold-chain item deliveries across dense urban centers."

### Example B.1 — "Risk-Averse Logistics Director" (Sentiment: mixed)
{{"persona": "{name}", "reaction": "The promise of sub-15-minute fulfillment across urban grids is incredibly valuable for our urgent medical inventory needs. However, relying on independent unvetted bicycle couriers means our cold-chain compliance guarantees are completely exposed to uncontrolled human variables.", "sentiment": "mixed", "key_objection": "Inability to strictly enforce medical temperature compliance across independent courier networks."}}

### Example B.2 — "Agile Operations Optimizer" (Sentiment: positive)
{{"persona": "{name}", "reaction": "Bypassing heavy commercial delivery vans completely bypasses downtown gridlock, giving us an instant operational velocity advantage. If the API exposes real-time telemetry coordinates for every single rider, we can integrate this into our dispatch layout by tomorrow afternoon.", "sentiment": "positive", "key_objection": "Availability of raw real-time telemetry coordinates through a standardized API."}}

## SCENARIO GAMMA: An Automated Dynamic Personalization Interface
Pitch Context: "A web optimization script that monitors a user's peripheral cursor friction, scrolling speed, and navigation pauses to completely restructure a website layout in real time for optimal conversion."

### Example C.1 — "Privacy-First Technical Advocate" (Sentiment: negative)
{{"persona": "{name}", "reaction": "Tracking micro-movements of cursor friction and pacing patterns is indistinguishable from intrusive telemetry tracking. Users will notice the disorienting, shifting layout changes immediately, triggering deep distrust and forcing them to drop off our page entirely.", "sentiment": "negative", "key_objection": "Intrusive biometric tracking behavior that actively damages user trust metrics."}}

### Example C.2 — "Conversion-Obsessed Growth Lead" (Sentiment: mixed)
{{"persona": "{name}", "reaction": "If this dynamically simplifies complicated checkout funnels for confused or slower users, our landing page conversion rates will jump significantly. But if the script injects even a 50-millisecond delay into our initial page-load budget, the latency penalty will wipe out any conversion gains.", "sentiment": "mixed", "key_objection": "Initial JavaScript execution overhead and its subsequent impact on page-load speed metrics."}}

# CORE OBJECTIVE ANALYSIS MANDATE
Synthesize all rules, structural styles, constraints, step protocols, and identity restrictions documented above. Ensure your vocabulary matches the specific professional, financial, or technical domain of your profile. Undergo your silent reasoning process now, and construct your response to the user's pitch text.

# TARGET INPUT MATCH SPECIFICATION
Review the target idea pitch provided below. Evaluate its details against your character profile, and return the final structured response block.

## THE IDEATION PROPOSAL TO RECOVERY PITCH:
{idea}

# FINAL SYSTEM OUTPUT FORMULATION SPECIFICATION
Respond exclusively with a single, perfectly formatted, minified, valid JSON object. Do not include markdown block ticks like ```json, do not introduce trailing commas, do not output any surrounding text, and avoid any introductory prose.

{{"persona": "{name}", "reaction": "<Your 2-3 sentence, highly specific, voice-aligned, priority-driven analytical response text>", "sentiment": "positive|mixed|negative", "key_objection": "<The single, granular structural bottleneck or absolute prerequisite feature for your profile>"}}
"""

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
# RETRY HELPER (M4): exponential backoff + jitter for transient API errors.
# Re-raises the last error if all attempts fail, so the degrade chain (or
# _safe_json fallback) can catch it.
# ----------------------------------------------------------------------
def _with_retries(fn, attempts=3, base_delay=1.0):
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — broad on purpose for transient API errors
            last_err = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i) + random.uniform(0, 0.5))
    raise last_err

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
# PROMPT CACHING (M4): the persona system PREFIX (everything before the idea
# marker) is large (~2.2K tokens) and IDENTICAL across runs for each of the 5
# fixed personas. Explicit context caching bills the cached prefix at ~10% of
# input price -> ~90% input cost reduction on the repeated part (measured in
# isolation at ~2049/2070 prompt tokens cached).
#
# This template puts {idea} in the MIDDLE, with the output-format spec AFTER it.
# The cacheable PREFIX is everything before the idea marker; the variable SUFFIX
# is the idea + the format spec that follows. We cache the prefix as a
# system_instruction and send the suffix as the per-call content.
#
# Safety: caching is Gemini-only and OPTIONAL. Any failure falls back to a normal
# uncached Gemini call, so the demo never breaks. Caches are used only on
# google/* degrade hops; OpenAI/Anthropic fallbacks send the full prompt
# uncached. A failed prefix is remembered so we don't retry creation every call.
# Toggle with USE_PROMPT_CACHE.
# ----------------------------------------------------------------------
USE_PROMPT_CACHE = True
PERSONA_CACHE_TTL = "3600s"             # 1 hour (session-long)
CACHE_MODEL = "gemini-2.5-flash-lite"   # caches are model-specific
_IDEA_MARKER = "## THE IDEATION PROPOSAL TO RECOVERY PITCH:"

_persona_cache_names = {}   # prefix string -> cache resource name
_cache_failed = set()       # prefixes that failed creation (don't retry every call)
_cache_lock = threading.Lock()


def _split_prefix_suffix(full_system):
    """Split a rendered persona prompt at the idea marker.
      prefix = stable text BEFORE the idea (cached)
      suffix = the idea + everything after it (sent per call)
    If the marker is absent, prefix = whole prompt, suffix = ''."""
    if _IDEA_MARKER in full_system:
        i = full_system.index(_IDEA_MARKER)
        return full_system[:i].rstrip(), full_system[i:]
    return full_system, ""


def _create_cache_for(prefix):
    """Create one explicit cache for a persona prefix; return its resource name
    (or None on failure, so callers fall back to uncached)."""
    try:
        from google import genai
        from google.genai import types
        client = genai.Client()
        cache = client.caches.create(
            model=CACHE_MODEL,
            config=types.CreateCachedContentConfig(
                system_instruction=prefix,
                ttl=PERSONA_CACHE_TTL,
            ),
        )
        logger.info("prompt cache created: %s (%s cached tokens)",
                    cache.name, getattr(cache.usage_metadata, "total_token_count", "?"))
        return cache.name
    except Exception as e:  # noqa: BLE001
        logger.warning("prompt cache creation failed: %s", e)
        return None


def warm_persona_caches():
    """Eagerly create all 5 persona caches up front (call once at session start,
    e.g. from app.py). Safe to call repeatedly; skips mock mode and no-ops if
    caching is disabled. Never raises — failures just mean uncached calls."""
    if USE_MOCKS or not USE_PROMPT_CACHE:
        return
    for p in PERSONAS:
        full = PERSONA_SYSTEM_TEMPLATE.format(
            name=p["name"], stance=p["stance"],
            priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea="")
        prefix, _ = _split_prefix_suffix(full)
        _get_or_create_cache(prefix)


def _get_or_create_cache(prefix):
    """Return a cache name for this prefix, creating lazily if needed.
    Remembers failures so it won't retry a doomed creation on every call.
    Returns None if caching is off, mock mode, or creation failed."""
    if not USE_PROMPT_CACHE or USE_MOCKS:
        return None
    with _cache_lock:
        name = _persona_cache_names.get(prefix)
        if name:
            return name
        if prefix in _cache_failed:
            return None
        name = _create_cache_for(prefix)
        if name:
            _persona_cache_names[prefix] = name
        else:
            _cache_failed.add(prefix)  # don't hammer creation every call
        return name


def _call_gemini_cached(model, system, user, persona_name=None):
    """Gemini persona call using an explicit cache for the stable prefix.
    Sends the suffix (idea + format spec) as content. Falls back to a normal
    uncached call if caching is unavailable or the cached call fails."""
    prefix, suffix = _split_prefix_suffix(system)
    cache_name = _get_or_create_cache(prefix)

    if cache_name:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client()
            resp = client.models.generate_content(
                model=model,
                contents=suffix if suffix else user,
                config=types.GenerateContentConfig(cached_content=cache_name),
            )
            return resp.text
        except Exception as e:  # noqa: BLE001 — cache may have expired; drop & recreate next time
            logger.warning("cached gemini call failed (%s); dropping cache, running uncached",
                           type(e).__name__)
            with _cache_lock:
                _persona_cache_names.pop(prefix, None)
    # Uncached fallback (also the path when caching is disabled/unavailable).
    return _call_gemini(model, system, user)

# ----------------------------------------------------------------------
# PERSONA DEGRADE CHAIN (M4): a 503 on one model shouldn't kill the panel.
# Degrade across MODELS, then PROVIDERS, then to a soft placeholder.
#   gemini-2.5-flash-lite -> gemini-2.5-flash -> gpt-4o-mini
#     -> claude-haiku-4-5 -> placeholder (panel returns 4/5 instead of crashing)
# Each hop wrapped in _with_retries. Only persona calls degrade; moderator and
# strategist keep their single-model paths.
# ----------------------------------------------------------------------
PERSONA_DEGRADE_CHAIN = [
    ("google",    "gemini-2.5-flash-lite"),
    ("google",    "gemini-2.5-flash"),
    ("openai",    "gpt-4o-mini"),
    ("anthropic", "claude-haiku-4-5"),
]

_PROVIDER_DISPATCH = {
    "google":    _call_gemini,
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
}


def _persona_placeholder(name):
    """Returned only when every live hop has failed. Keeps the panel intact
    (4/5 instead of a crash) and is flagged so it can't pollute diagnostics."""
    return json.dumps({
        "persona": name,
        "reaction": "(This panelist was unavailable — all model providers failed for this call.)",
        "sentiment": "mixed",
        "key_objection": "n/a — provider outage",
        "_degraded": True,
    })


def _call_persona_with_degrade(system, user, persona_name):
    """Walk the degrade chain for one persona call. Each hop gets _with_retries;
    on final failure step to the next provider/model. Exhausted -> placeholder.
    Gemini hops use the CACHED caller (explicit prompt caching); OpenAI/Anthropic
    fallbacks send the full prompt uncached (they can't read a Gemini cache)."""
    for provider, model in PERSONA_DEGRADE_CHAIN:
        if provider == "google":
            fn = lambda m=model: _call_gemini_cached(m, system, user, persona_name)
        else:
            base = _PROVIDER_DISPATCH[provider]
            fn = lambda b=base, m=model: b(m, system, user)
        try:
            return _with_retries(fn)
        except Exception as e:  # noqa: BLE001
            logger.warning("persona degrade: %s/%s failed for '%s' (%s); trying next hop",
                           provider, model, persona_name, type(e).__name__)
            continue
    logger.error("persona degrade: ALL hops failed for '%s'; using placeholder", persona_name)
    return _persona_placeholder(persona_name)

# ----------------------------------------------------------------------
# AGENTS
# ----------------------------------------------------------------------
def run_persona_panel(idea):
    """Run personas concurrently, with degrade fallback.
    Mock mode keeps full concurrency and skips(instant + free)."""
    def one(p):
        system = PERSONA_SYSTEM_TEMPLATE.format(
            name=p["name"], stance=p["stance"],
            priorities=", ".join(p["hidden_priorities"]), voice=p["voice"], idea=idea)
        if USE_MOCKS:
            raw = _mock_persona_for(p["name"])(idea)
        else:
            _rate_gate()  # throttle only matters for real API calls
            raw = _call_persona_with_degrade(system, idea, p["name"])
        return _safe_json(raw, fallback={"persona": p["name"], "reaction": raw,
                                         "sentiment": "mixed", "key_objection": "n/a"})
    workers = len(PERSONAS) if USE_MOCKS else PERSONA_MAX_WORKERS
    with ThreadPoolExecutor(max_workers=workers) as ex:
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
    idea = "A free, open-source browser extension that instantly adds accessibility alt-text to every image on a page — runs 100% on-device with no data leaving your browser, no account, no setup, and a one-click toggle. Nothing changes on the underlying site, so there's nothing to break or migrate."
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