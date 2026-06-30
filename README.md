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
- **NVIDIA NIM**: open [build.nvidia.com](https://build.nvidia.com), make a free
  developer account (no card), and copy your `nvapi-` key. Gives you DeepSeek and
  80+ other models.

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

# Or if you used NVIDIA instead (DeepSeek with tool calling):
# SCOUT_MODEL=nvidia_nim/deepseek-ai/deepseek-v3.2-exp
# NVIDIA_NIM_API_KEY=nvapi-paste_your_key_here
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

## Tool library

Beyond web search and fetch, Scout ships a pluggable library of specialized
OSINT tools. At mission start it **auto-detects which tools are usable** - based
on the keys, packages, and binaries you have - and hands only those to the
agents (same idea as model discovery). Run `scout tools` to see live status.

Keyless tools work out of the box; the rest light up when you add a key, install
an extra (`pip install "scout[osint]"`), or point Scout at a cloned repo.

If a mission would clearly benefit from a tool you haven't enabled, Scout
**tells you** - at the start of the run and in the report it lists the relevant
unconfigured tools and the exact step to turn each one on.

Looking for more tools to add? `scout discover` queries GitHub for the
top-starred OSINT repos and flags which Scout already integrates, so you can
spot strong new candidates to wrap into the registry (`scout discover phone` to
focus the search). The agents themselves
work the mission by every legitimate means (reasoning, web search/fetch, reading
your files, asking you), and reach for a specialized tool whenever the task is
something that tool is built for.

| Tool | Category | What it's for | Needs |
|---|---|---|---|
| airplanes.live | aviation | Live ADS-B flight tracking (incl. military) | nothing (free) |
| web-check | web recon | DNS, SSL, headers, WHOIS, ports for a domain | nothing (free) |
| Reddit (PullPush) | social | User history + search, incl. removed content | nothing (free) |
| Data-broker opt-out | data hygiene | Removal links for people-search brokers | nothing (free) |
| GDELT News | news | Near-real-time global news/event search | nothing (free) |
| Telegram OSINT | social | Read public Telegram channel posts | nothing (free) |
| Crypto Wallet Trace | crypto | BTC/ETH balance + activity via explorers | nothing (free) |
| NVD CVE Lookup | cyber | CVEs by id or product keyword (CVSS) | nothing (free) |
| Scrapling | web recon | Anti-bot / stealth scraping | `pip install scrapling` |
| GeoCLIP | geolocation | Open-source image → GPS, offline | `pip install geoclip` |
| image-matching-webui | imagery | Feature-match two images to corroborate scenes | `pip install imcui` |
| Presidio | data hygiene | Redact PII from collected text | `pip install presidio-analyzer` |
| BBOT ⚠ | recon | Recursive attack-surface / subdomain recon | `pip install bbot` |
| GHunt | accounts | Google account footprint from an email | `pip install ghunt` + login |
| tookie-osint | accounts | Username → accounts across many sites | clone repo, set `SCOUT_TOOKIE_PATH` |
| maigret | accounts | Deep username dossier (3,000+ sites, profile parsing) | `pip install maigret` |
| Blackbird | accounts | Fast username/email search (WhatsMyName, 600+ sites) | clone repo, set `SCOUT_BLACKBIRD_PATH` |
| holehe | email | Which of 120+ sites an email is registered on | `pip install holehe` |
| theHarvester | email | Emails/names/subdomains for a domain | `pip install theHarvester` |
| PhoneInfoga | phone | Phone-number validation + footprint | `phoneinfoga` binary on PATH |
| dnstwist | web recon | Typosquat / lookalike / phishing domains | `pip install dnstwist` |
| Photon | web recon | Crawl a site for emails/handles/links/secrets | clone repo, set `SCOUT_PHOTON_PATH` |
| Instaloader | social | Public Instagram profile metadata | `pip install instaloader` |
| Toutatis ⚠ | social | Deep Instagram extraction (email/phone) | `pip install toutatis` + `TOUTATIS_SESSION_ID` |
| subfinder | web recon | Fast passive subdomain enumeration | `subfinder` binary on PATH |
| httpx | web recon | Probe hosts for liveness/title/tech | ProjectDiscovery `httpx` binary (set `SCOUT_HTTPX_PATH` if it clashes with python `httpx[cli]`) |
| SpiderFoot ⚠ | recon | All-in-one OSINT engine (200+ modules) | clone repo, set `SCOUT_SPIDERFOOT_PATH` |
| geowifi | geolocation | Geolocate a WiFi BSSID/SSID | clone repo, set `SCOUT_GEOWIFI_PATH` |
| Robin ⚠ | dark web | LLM-driven dark-web search (needs Tor) | `robin` on PATH |
| OpenSanctions | sanctions | Screen names vs OFAC SDN / PEP / watchlists | `OPENSANCTIONS_API_KEY` (free for journalists/NGOs) |
| Grayhat Warfare ⚠ | exposure | Search exposed S3/Azure/GCS buckets | `GRAYHAT_API_KEY` |
| FaceCheck.ID ⚠ | facial recognition | Reverse face search (paid) | `FACECHECK_API_TOKEN` |
| GeoSpy ⚠ | geolocation | AI photo geolocation (commercial) | `GEOSPY_API_KEY` |
| MarineTraffic / Kpler | maritime | Vessel tracking by MMSI/IMO (commercial) | `MARINETRAFFIC_API_KEY` |

⚠ = carries legal/ethical/reputational weight (surveillance, facial recognition,
exposed data, dark web). Use responsibly, lawfully, and within each service's
terms. Control what's active with `SCOUT_TOOLS` / `SCOUT_DISABLE_TOOLS` (see
`.env.example`).

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
| A free NVIDIA key        | `nvidia_nim/deepseek-ai/deepseek-v3.2-exp` | `NVIDIA_NIM_API_KEY` (free, no card) |
| A Claude / Anthropic key | `anthropic/claude-sonnet-4-6` (or `anthropic/claude-opus-4-8`) | `ANTHROPIC_API_KEY`                  |
| An OpenAI key            | `openai/gpt-5.5`              | `OPENAI_API_KEY`                                          |
| Qwen on your home server (Ollama) | `ollama/qwen2.5:14b` | `SCOUT_API_BASE=http://host.docker.internal:11434`        |
| Any OpenAI-compatible server (vLLM, LM Studio, TGI) | `openai/<name>` | `SCOUT_API_BASE=http://host.docker.internal:8000/v1`      |
| Just want to see it run offline | `mock` | nothing (no key, scripted output) |

Free tiers (Groq, Gemini, NVIDIA NIM) are rate-limited but plenty for a test mission - see
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
