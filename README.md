# Persona Lab

A multi-agent synthetic focus group. Give it any open-ended idea and a panel of 5 distinct AI personas react and **disagree**; a **Moderator** clusters the reactions into themes; a **Strategist** turns the conflict into concrete recommendations. The disagreement is the point — a single LLM gives sycophantic consensus, while forced divergence across personas gives useful signal.

*Applied Generative AI (IE5374)*

## Architecture

| Step | Agent | Model | Role |
|---|---|---|---|
| 1 (×5, parallel) | Persona Panel | Gemini 2.5 Flash-Lite | high-volume reactions (free tier) |
| 2 | Moderator | GPT-4o-mini | cluster into themes (structured JSON) |
| 3 | Strategist | Claude Haiku 4.5 | recommendations (hardest reasoning) |

Cost-aware routing: each agent uses the cheapest model that fits its job. Total project cost: ~$0–3.

**Output contract:**
```python
run_persona_lab(idea) -> { "idea", "reactions", "moderation", "strategy" }
```

## Quick start (mock mode, $0, no installs)

```bash
git clone <REPO_URL>
cd persona-lab
jupyter notebook Persona_Lab_M1.ipynb   # run top-to-bottom
```

`USE_MOCKS = True` by default — the whole pipeline runs on canned responses with zero API calls. Build and test everything (including the UI) for free.

## Going live (M3)

```bash
pip install -r requirements.txt
cp .env.template .env        # then fill in the three keys
# set USE_MOCKS = False in the notebook / config
```

You need three keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. See `.env.template` for where to get each.

## Branches

- `main` — Branch per milestone, PR to merge.
- `feature/ui` - frontend: Streamlit UI, demo mode, deliverables.
- `feature/agents` — backend: live API wiring, agent logic, prompt tuning.

