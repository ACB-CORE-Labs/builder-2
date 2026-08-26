# builder-II Quickstart

Pure mechanics. The intended host contract is macOS Apple Silicon and Linux; Set 7 release rehearsal was qualified on macOS Apple Silicon and Debian Linux aarch64. Linux x86_64 support is not claimed as release-qualified by that rehearsal.

---

## 1. Prerequisites

- Python `>=3.12.13, <3.13`
- [`uv`](https://docs.astral.sh/uv/) (recommended package manager)
- Git
- *(Optional - macOS Apple Silicon)* Local MLX models via `uv sync --extra mlx`
- *(Optional - Linux / Remote)* [Ollama](https://ollama.com) or an OpenAI-compatible / Vertex endpoint

---

## 2. Install in 60 Seconds

```bash
# 1. Clone repository
git clone <repo-url> builder-2
cd builder-2

# 2. Install dependencies
uv sync --all-groups

# (Optional: Apple Silicon local MLX acceleration)
# uv sync --extra mlx

# 3. Initialize default configuration
cp .env.example .env
```

---

## 3. Verify Platform Health & Truth State

```bash
# Audit platform operational status
uv run builder-platform status

# Run system compliance checks
uv run builder doctor

# Inspect available target repository profiles
uv run builder-targets list
```

---

## 4. Run the Governed Smoke Test

Exercise the end-to-end closed loop (**propose $\rightarrow$ approve $\rightarrow$ verify $\rightarrow$ apply $\rightarrow$ rollback**) on a self-contained fixture repository:

```bash
bash scripts/clean-clone-smoke.sh
```

This smoke gate validates:
1. Target profile resolution.
2. Digest-bound patch proposal generation.
3. Interactive human-in-the-loop (HITL) approval boundary.
4. Bounded verification runner execution.
5. Preflight snapshot, patch application, and reverse-patch rollback.

---

## 5. Next Steps

- **Full First Session Walkthrough:** [`FIRST_SESSION.md`](FIRST_SESSION.md) — 30-minute clone-to-patch guided walkthrough.
- **Operator Concepts & Architecture:** [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) — The complete mental model and STRATUM TUI tour.
- **Terminology & Definitions:** [`docs/GLOSSARY.md`](docs/GLOSSARY.md) and [`LEXICON.md`](LEXICON.md).
