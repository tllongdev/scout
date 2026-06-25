```text
   ___  _________  __  _________
  / __/ / ___/ _ \/ / / /_  __/
 _\ \  / /__/ // / /_/ / / /
/___/  \___/\____/\____/ /_/   intelligence collector
```

A lightweight, containerized **agentic intelligence collector**. Give it a
mission in plain English; Scout reasons about where the intelligence lives,
sends a team of agents to collect it, maps what it finds into a graph, and
hands back a sourced report.

> A proof-of-concept for agentic data collection. Pull it, run it in Docker,
> point it at a goal, and watch agents plan, search, read, ask you for help when
> they're blocked, and assemble findings.

## How it works

```
mission brief
     │
     ▼
┌──────────┐   decomposes the goal into focused collection tasks
│ Planner  │   (reasons about web, APIs, local docs, and gated/offline sources)
└────┬─────┘
     │
     ▼
┌──────────┐   one agent per task, each with tools:
│Collectors│   web_search · web_fetch · local_files · ask_human
│          │   + records entities, relationships, observations as it goes
└────┬─────┘
     │
     ▼
┌──────────┐   draws sourced conclusions over the collected graph
│Synthesis │
└────┬─────┘
     │
     ▼
  output/  →  findings.md · graph.html · graph.json · raw_documents.json
```

Nothing is off the table as a source - including material that isn't on the
internet. When an agent needs credentials, access to a gated system, or
first-hand knowledge, it **pauses and asks you** right in the terminal.

## Bring your own model

Scout ships no credentials. You choose the model and supply your own key, so it
works with whatever you already pay for - or a model running on your own
hardware. Set this in `.env`:

| You have...            | `SCOUT_MODEL`                | Also set                                                  |
|------------------------|------------------------------|-----------------------------------------------------------|
| A Claude / Anthropic key | `anthropic/claude-sonnet-4-6` (or `anthropic/claude-opus-4-8`) | `ANTHROPIC_API_KEY`                  |
| An OpenAI key            | `openai/gpt-5.5`              | `OPENAI_API_KEY`                                          |
| A Gemini key             | `gemini/gemini-3.5-flash`     | `GEMINI_API_KEY`                                          |
| Qwen on your home server (Ollama) | `ollama/qwen2.5:14b` | `SCOUT_API_BASE=http://host.docker.internal:11434`        |
| Any OpenAI-compatible server (vLLM, LM Studio, TGI) | `openai/<name>` | `SCOUT_API_BASE=http://host.docker.internal:8000/v1`      |

### Not sure which model string to use?

Scout can list the models your credentials can actually reach - it asks each
provider's own API (and your local Ollama box), so you get real, current options
rather than a guess:

```bash
docker compose run --rm scout models
```

And if you run a mission without `SCOUT_MODEL` set, Scout discovers your
available models and lets you pick one interactively for that run.

## Quick start

```bash
# 1. Configure your model + key
cp .env.example .env
$EDITOR .env

# 2. (Optional) drop offline/private documents the agent may read
mkdir -p sources
cp ~/some-dossier.txt sources/

# 3. Run a mission
./run.sh "Map the leadership and funding relationships of the top 5 AI safety nonprofits"
```

Or without the helper script:

```bash
docker compose build
docker compose run --rm scout "Your mission here"
```

Results land in `./output/mission-<date>-<id>/`:

- `findings.md` - the report: summary, ranked findings, entities, relationships
- `graph.html` - interactive intelligence graph (open in a browser)
- `graph.json` - the graph as node-link data
- `raw_documents.json` - every source collected, verbatim, for audit

## Tuning

Set these in `.env`:

- `SCOUT_MAX_TASKS` - how many collection tasks the planner may create (default 6)
- `SCOUT_MAX_STEPS` - max tool calls per collector agent (default 12)
- `SCOUT_TEMPERATURE` - model temperature (default 0.4)

## Local development (without Docker)

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env   # add your model + key
scout "Your mission here"
```

## Notes

- This is a POC. Be a good citizen: respect site terms, rate limits, and the law.
- The `ask_human` flow makes Scout safe around credentials - it never invents
  secrets; it asks, and you can mask the input.
- Graph quality scales with model quality. A frontier model produces noticeably
  richer entity/edge extraction than a small local one.
