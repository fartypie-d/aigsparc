# aigsprac

> formerly **dev-orchestrate-kit**

**English** | [한국어](./README.ko.md)

> **Turn multiple AI subscriptions into one development pipeline.** A supervisor harness
> (Claude or Codex) does only planning and review; implementation is auto-delegated to
> opencode agents running on the subscriptions you already pay for (GPT, Grok, Qwen) —
> and when one subscription hits its limit, the chain falls back to the next quota pool.
> One script adopts it into any existing project.

![license](https://img.shields.io/badge/license-MIT-green)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-blue)
![shell](https://img.shields.io/badge/bash-3.2%2B-lightgrey)
![harness](https://img.shields.io/badge/harness-claude%20%7C%20codex-8A2BE2)

A bootstrap kit that reproduces this development environment on any machine. It layers a
custom orchestration stack (onboarding command, model fallback chains, project scaffolding)
on top of [everything-claude-code](https://github.com/affaan-m/everything-claude-code) and
[superpowers](https://github.com/obra/superpowers).

## The AI General Staff practice

aigsprac = "AI General Staff practice". The supervisor harness is the general
staff — it only plans, reviews, and approves; implementation is carried out by
delegated field agents (opencode) running on the subscriptions you already pay for.

## Why

**If Claude Code tokens feel expensive — stop burning Opus on mechanical implementation and
delegate it to the other subscriptions you already pay for.** The workflow this kit sets up
has three layers:

1. **Cross-subscription token optimization** — the supervisor (Claude) spends tokens only on
   planning, review, and approval gates; actual implementation is delegated through opencode
   to GPT / Grok / Qwen subscriptions. Different subscriptions are **separate quota pools**,
   so when one hits a limit the chain automatically falls back to the next provider and work
   never stalls.
2. **Automated project onboarding** — one `/orchestrate-onboard` run detects the real stack
   and generates the agent roster, delegation agents, reviewer mappings, and custom skills.
   Use `new-project.sh` for new projects or `adopt-project.sh` for existing ones —
   **non-destructive** (never overwrites existing files).
3. **A browser for headless servers** — a stealth CDP + escalating-fetch container for dev
   servers with no X display, GPU, or per-user Chrome. Usable **independently** of the
   orchestration workflow (see below).

## Prerequisites

- **One supervisor subscription** — either a **Claude plan** (Pro / Max) for Claude Code, or
  an **OpenAI plan** for Codex CLI. `--plan=pro|max5|max20` tunes token profiles to your
  Claude plan.
- **At least one delegation provider** — they are interchangeable; each one you add deepens
  the fallback pool:

  | Provider | What you need | Wire-up |
  |---|---|---|
  | OpenAI (GPT) | ChatGPT subscription | `opencode auth login -p openai` (OAuth) |
  | xAI (Grok) | subscription | `opencode auth login -p xai` (OAuth) |
  | Qwen / DeepSeek | API key | `QWEN_API_KEY` in `~/.config/opencode/secrets.env` |
  | Gemini (antigravity proxy) | API key + proxy | `ANTIGRAVITY_API_KEY` — the proxy (:8045) is not bundled; bring your own, see [PORTING](docs/PORTING.md) |

  A supervisor-side OpenAI subscription can double as a delegation provider — one
  subscription, two roles.
- **Tools** — bash 3.2+, git, python3, jq, and the [opencode](https://opencode.ai) CLI.
  Docker is only needed for the optional containers and the usage dashboard.

## Quick start

```bash
git clone https://github.com/fartypie-d/aigsprac.git
cd aigsprac

# Once per machine — installs global assets under $HOME; harness/provider choices are
# auto-detected or asked interactively if omitted (harness = supervisor-side Claude Code and/or Codex;
# opencode is always installed as the delegation executor)
./install.sh --claude --providers=qwen,openai --plan=max20 typescript python

# Per project — pick one of the two entry points to apply the kit to a project directory
./new-project.sh   ~/my-new-project      # starting fresh
./adopt-project.sh ~/existing-project    # already in progress (non-destructive)

# Then open the harness inside the project (with the smartest model) and run
/orchestrate-onboard
```

## How it works

```mermaid
flowchart LR
    U[Developer] --> S[Supervisor harness<br/>Claude / Codex]
    S -->|plan · task specs| RD[run-delegation.sh]
    RD -->|project/host model-policy.json<br/>tier chain via -m| OC[opencode delegate agent]
    OC -->|primary| GPT[openai · GPT]
    OC -->|fallback| XAI[xai · Grok]
    OC -->|fallback| QW[qwen · Qwen]
    OC -->|artifacts| RV[Reviewer gate]
    RV -->|PASS| C[Gated commit]
    RV -->|REJECT| RD
    S -. supervision · review only .-> RV
```

- **The supervisor never implements.** Source changes go through `run-delegation.sh` to
  opencode and come back through a reviewer: ECC reviewer subagents under Claude,
  `codex-review.sh` under Codex.
- **Models are centrally governed.** `run-delegation.sh` first looks for
  `<git-top-level>/.claude/model-policy.json` (or `<caller-cwd>/.claude/model-policy.json` when
  the caller is outside a Git repository), then falls back to
  `~/.config/opencode/model-policy.json`. It injects the selected tier chain via `-m` and logs
  `POLICY_USED=<path> (project|host)` to stdout and the `.wrapper` log. Quota/credit failures
  (including `status 402`, `insufficient credits`, `credit balance is too low`, and
  `usage limit reached`) and hangs trigger automatic fallback. Chains are generated by
  `gen-policy.sh` and live-verified by `model-doctor.sh` (so a typo'd model ID can't silently eat
  your fallbacks). If neither policy exists, the command exits 64 and reports both candidate
  paths. `model-doctor.sh` defaults to the host policy; to verify a project policy, pass
  `--policy .claude/model-policy.json`.

  The project policy is tracked and committed with the repository, so anyone who can change
  `.claude/model-policy.json` can influence delegation model selection; review that file's diff
  at the same level as code changes. When invoking delegation from a submodule or nested
  repository, run it from the intended repository root: `git rev-parse --show-toplevel` otherwise
  points at the nested root and cannot find the outer project's `.claude/`.

### Which doctor checks what?

Use the three diagnostics for different boundaries; `kit-doctor.sh` does **not** check models,
authentication, hooks, or containers, so running it does not mean that everything is healthy.

| Tool | What it checks | Call |
|---|---|---|
| `kit-doctor.sh` | Required/optional tool presence, global asset presence, and drift from the kit source | `./install.sh --doctor` or `bash scripts/kit-doctor.sh` |
| `model-doctor.sh` | Model policy, fallback chain, and provider authentication | `~/.config/opencode/model-doctor.sh` |
| `hook-selfcheck.sh` | Project hook (guard) survival | `bash scripts/hook-selfcheck.sh` |

To fill only missing kit assets, run `./install.sh --doctor --add-missing` or `bash scripts/kit-doctor.sh --add-missing`. This never
overwrites an existing file, even when its contents differ. To update drift, rerun `./install.sh`.

`install.sh` allows `--doctor` only with `--claude`, `--codex`, or `--add-missing`; with `--containers=`, `--providers=`, `--plan=`, or an ECC language positional argument, it rejects the request before diagnosis to prevent users from mistaking it for a completed installation.

The doctor exit code is a CI gate signal:

| Exit code | Meaning |
|---|---|
| `0` | No FAIL (WARN and DRIFT may still be present) |
| `1` | A FAIL exists (missing required tool, missing checked asset, containment violation, etc.) |
| `64` | Usage error (unknown option or an invalid combination of `--doctor` and installation options) |

Do not combine the CI health check with the test-only hook `INSTALL_PARSE_ONLY=1`:
`INSTALL_PARSE_ONLY=1 ./install.sh --doctor --claude` prints parse results and exits `0` without
running the actual diagnosis, which can make a CI health check silently pass.
- **Parallel delegation is safe by construction.** With an `opencode serve` daemon
  (managed by `opencode-serve-ctl.sh`), delegations attach to the server and are locked
  **per project** — different projects run in parallel, the same project stays serial.
  Without a server it falls back to standalone mode under a global lock, because concurrent
  bare `opencode run` processes die silently on a session-DB conflict.
- **The project roster is the single source of truth.** `.claude/orchestrate.md` maps agents,
  reviewers, and verification commands; both harnesses share it. **No roster, no delegation.**

### Workflow in detail

One full phase cycle — the left lane is everything the user actually does (one instruction,
a few multiple-choice answers, two approvals). The full walkthrough with all five diagrams
lives in [docs/WORKFLOW.md](./docs/WORKFLOW.md) (Korean: [docs/WORKFLOW.ko.md](./docs/WORKFLOW.ko.md)).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fig-flow-en-dark.svg">
  <img alt="Full workflow: user, supervisor harness, and opencode lanes with two approval gates" src="docs/assets/fig-flow-en.svg">
</picture>

## Harness combinations

Both combinations use opencode as the implementation executor; the choice selects the
supervisor (orchestrator) harness.

| Combo | Install | Review | Enforced hooks |
|---|---|---|---|
| Claude + opencode | `./install.sh --claude` | ECC reviewer subagents | bash-guard · post-edit-check |
| Codex + opencode | `./install.sh --codex` | `scripts/codex-review.sh` | none — replaced by sandbox/approval |

## Layout

| Path | Contents |
|---|---|
| `install.sh` | Global install — harness/provider/container/plan selection, idempotent |
| `new-project.sh` / `adopt-project.sh` | The two entry points. Never overwrite existing files |
| `lib/stamp.sh` | Scaffolding functions shared by both entry scripts |
| `core/scripts/` | Harness-agnostic scripts — `run-delegation.sh`, `phase-tools.py`, … |
| `core/opencode/` | Provider mapping table, chain generator, `model-doctor.sh`, seed profiles |
| `core/skillpack/` | Skill-pack update detection config seed (consumed by `skillpack-update-check.sh`) |
| `core/onboard/` | `/orchestrate-onboard` procedure body (single source) |
| `core/project-template/` | Roster, agent conventions, docs system (harness-agnostic) |
| `adapters/claude/` | Global skills + project hooks, settings, CLAUDE.md, plan profiles |
| `adapters/codex/` | `~/.codex/prompts` + `.codex/` project layer, `codex-review.sh` |
| `containers/browser/` | Stealth CDP + escalating fetch API (git submodule → [insane-cloak](https://github.com/fartypie-d/insane-cloak)) |
| `components/usage-dashboard` | Session usage observability dashboard (git submodule) |

## usage-dashboard — session observability (submodule)

A local web dashboard that analyzes Claude Code + opencode session usage
([fartypie-d/usage-dashboard](https://github.com/fartypie-d/usage-dashboard)):
model mix and cost, cache efficiency, delegation chains, and session health. It reads the
`.orchestrate/events.jsonl` event log this kit emits to reconstruct the delegation tree
without log parsing.

The installer is the recommended setup path:

```bash
./install.sh --containers=dashboard    # or pick it in the installer wizard
# For browser + dashboard: ./install.sh --containers=browser,dashboard
# http://127.0.0.1:9280 (localhost only)
```

The installer initializes the `components/usage-dashboard` submodule, checks Docker,
Compose, and the port (default `9280`; set `INSTALL_DASH_PORT` to override the port
pre-check), then asks for confirmation before running `docker compose up -d`. If the
container fails to start, installation continues and the remaining manual steps include
a retry command for the failed container only.

If you want to start Docker later or are not using the installer, use the manual path:

```bash
git submodule update --init components/usage-dashboard
cd components/usage-dashboard
docker compose build && docker compose up -d
# http://127.0.0.1:9280 (localhost only)
```

After migrating an existing `DOCs` project to `docs/phases`, change `docs_dir` to
`docs/phases` in `~/.local/state/orchestrate/registry/<project>.json` and recreate the mount.

Development happens in its own repository; this kit only bumps the submodule pointer at
release time.

### Dashboard document mounts

The dashboard opens each project's progress documents at the host absolute path recorded in the
orchestrate registry. That path must also be mounted at the same path inside the container;
otherwise the UI shows “No documents”. `./install.sh --containers=dashboard` reads the registry,
automatically generates the dashboard Compose override, and applies it when the file exists.
By default it writes `~/.local/state/orchestrate/dashboard-compose.override.yml`; when
`ORCH_STATE_DIR` is set, it writes under that directory instead.

After registering a new project or changing a DOCs path, regenerate the mounts and restart the
dashboard from the repository root:

```bash
python3 scripts/phase-tools.py dashboard-mounts
docker compose -f components/usage-dashboard/docker-compose.yml \
  -f ~/.local/state/orchestrate/dashboard-compose.override.yml up -d
```

Non-existent DOCs directories are skipped, so Docker does not create root-owned empty directories
on the host. Mounts are read-only (`ro`) and asymmetric: the source resolves symlinks to the real
path, while the target keeps the registry path the dashboard opens. If you replace a symlink,
regenerate the override before restarting the dashboard.

## Standalone module — the browser container

The browser container lives in its own repository,
[insane-cloak](https://github.com/fartypie-d/insane-cloak), referenced here as the
`containers/browser` submodule. Even without the orchestration workflow it works on its own —
it exists for headless dev servers that need a browser but have no X display, GPU, or
per-user Chrome:

```bash
git submodule update --init containers/browser   # once, to fetch the submodule
cd containers/browser
bash insane-api/vendor/sync-vendor.sh    # vendor the upstream MIT engine at a pinned commit
docker compose up -d
# 127.0.0.1:9222 raw CDP · 127.0.0.1:9223 escalating fetch API
```

Need to see the screen? Add the noVNC overlay (`docker-compose.novnc.yml`, pinned to
127.0.0.1, view-only). Details and security notes: `containers/browser/README.md`.

### Using it over MCP

Point `chrome-devtools-mcp` at the container's CDP (`:9222`) and a harness like Claude Code
drives the browser directly. The MCP server does not spawn its own browser, so the stealth
fingerprint and the session are preserved.

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--browserUrl", "http://127.0.0.1:9222"]
    }
  }
}
```

To isolate per caller, append `?fingerprint=<name>` to `--browserUrl`. Full details, including
security notes, are in the MCP section of `containers/browser/README.md`.

## Token profiles per Claude plan

`--plan=pro|max5|max20` assigns models to match your plan. Subagent tiering is done **only**
via the agent frontmatter `model:` field (`CLAUDE_CODE_SUBAGENT_MODEL` is forbidden — it
demotes reviewers too). **The quality gate (reviewers) stays on sonnet under every plan** —
savings come from the worker class and thinking budgets.

## Cross-machine sync convention

- **This repository is the single source.** Improve an orchestration asset on any machine →
  commit to the kit → push → pull on other machines and re-run `./install.sh` (idempotent).
- Don't hand-edit `~/.claude/skills/orchestrate` and call it done — the next install reverts it.
- **Exception — the browser container is a separate repository.** Fix the container on the dev
  host first, mirror it into [insane-cloak](https://github.com/fartypie-d/insane-cloak), then
  bump only the `containers/browser` submodule pointer here.
- **Exception — model-policy has two scopes.** A committed project
  `.claude/model-policy.json` takes precedence; when it is absent, the generated host policy
  `~/.config/opencode/model-policy.json` is used. The host policy's source of truth remains the
  `core/opencode/provider-models.json` mapping table.
- Never included: secrets (`secrets.env`), subscription OAuth (per-machine login), memory and
  project data.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Acknowledgements

This kit is assembled on top of the following open-source projects — all MIT licensed:

| Project | Role | License |
|---|---|---|
| [everything-claude-code](https://github.com/affaan-m/everything-claude-code) | Rules, agents, reviewer base layer | MIT |
| [superpowers](https://github.com/obra/superpowers) | Skills and workflows (brainstorming, TDD, SDD, …) | MIT |
| [opencode](https://opencode.ai) | Multi-provider delegation CLI | — |
| [insane-search](https://github.com/fivetaku/insane-search) | Escalating fetch engine (vendored into the browser container) | MIT |
| [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) | Stealth Chromium (browser container base) | MIT |

Copyright and license notices for each project are preserved in the vendored tree
(`containers/browser/insane-api/vendor/LICENSE`) and in each installed repository.

## License

[MIT](./LICENSE) © fartypie-d
