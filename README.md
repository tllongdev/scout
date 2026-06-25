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

## Get started free (about 2 minutes)

No paid account, no credit card. Scout runs on free model tiers. You need
[Docker](https://docs.docker.com/get-docker/) and [git](https://git-scm.com/downloads).

**1. Get a free API key** (pick one):

- **Groq** (recommended - fastest): open [console.groq.com/keys](https://console.groq.com/keys),
  sign in with Google or email, click **Create API Key**, and copy the key (it
  starts with `gsk_`).
- **Google Gemini**: open [aistudio.google.com/apikey](https://aistudio.google.com/apikey),
  sign in, click **Create API key**, and copy it.

**2. Get the code and config file:**

```bash
git clone https://github.com/tllongdev/scout.git
cd scout
cp .env.example .env
```

**3. Paste your key into `.env`.** Open `.env` in any editor and set the two
lines for the provider you chose:

```bash
# If you used Groq:
SCOUT_MODEL=groq/llama-3.3-70b-versatile
GROQ_API_KEY=gsk_paste_your_key_here

# Or if you used Gemini instead:
# SCOUT_MODEL=gemini/gemini-2.5-flash
# GEMINI_API_KEY=paste_your_key_here
```

**4. Run your first mission:**

```bash
./run.sh "Investigate Acme Robotics and its key partners"
```

That's it. Results land in `./output/`: a `findings.md` report and an
interactive `graph.html` you can open in your browser.

> No key yet and just want to watch it run? Use `SCOUT_MODEL=mock ./run.sh "..."`
> - it runs the whole pipeline with scripted, illustrative output (no key, no cost).

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

> **For best results, use a frontier model.** Scout's planning, multi-step tool
> use, and synthesis get sharply better with model quality. We recommend
> **Claude Sonnet 4.6** for the best balance of depth, speed, and cost, or
> **Claude Opus 4.8** for maximum extraction depth. The free Groq and Gemini
> tiers are great for trying Scout out - just expect richer graphs from a
> frontier model.

| You have...            | `SCOUT_MODEL`                | Also set                                                  |
|------------------------|------------------------------|-----------------------------------------------------------|
| **Nothing - want a free real model** | **`groq/llama-3.3-70b-versatile`** | **`GROQ_API_KEY`** (free, no card) |
| A free Gemini key        | `gemini/gemini-2.5-flash`     | `GEMINI_API_KEY` (free tier)                             |
| A Claude / Anthropic key | `anthropic/claude-sonnet-4-6` (or `anthropic/claude-opus-4-8`) | `ANTHROPIC_API_KEY`                  |
| An OpenAI key            | `openai/gpt-5.5`              | `OPENAI_API_KEY`                                          |
| Qwen on your home server (Ollama) | `ollama/qwen2.5:14b` | `SCOUT_API_BASE=http://host.docker.internal:11434`        |
| Any OpenAI-compatible server (vLLM, LM Studio, TGI) | `openai/<name>` | `SCOUT_API_BASE=http://host.docker.internal:8000/v1`      |
| Just want to see it run offline | `mock` | nothing (no key, scripted output) |

Free tiers (Groq, Gemini) are rate-limited but plenty for a test mission - see
[Get started free](#get-started-free-about-2-minutes) above for the 2-minute
setup. For heavy runs, use a paid or local model. The `mock` option runs the
full pipeline with scripted output and needs no key at all.

### Not sure which model string to use?

Scout can list the models your credentials can actually reach - it asks each
provider's own API (and your local Ollama box), so you get real, current options
rather than a guess:

```bash
docker compose run --rm scout models
```

And if you run a mission without `SCOUT_MODEL` set, Scout discovers your
available models and lets you pick one interactively for that run.

## Running missions

Already set up (see [Get started free](#get-started-free-about-2-minutes))? A few
more ways to run:

```bash
# Give agents offline/private documents to read (optional)
mkdir -p sources
cp ~/some-dossier.txt sources/

# Run a mission
./run.sh "Map the leadership and funding relationships of the top 5 AI safety nonprofits"

# Or without the helper script
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
