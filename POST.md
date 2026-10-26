*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

**FirstPick** finds beginner-friendly GitHub issues in open-source AI repos and hands me the 5 best ones, explained in plain English by a model running on my own machine.

Finding a first issue is slow and discouraging. You search "good first issue", open ten tabs, and find that half are closed, assigned, already have a PR, or have a comment saying "can I work on this?" from three weeks ago. FirstPick does that digging for me:

- **Collects** open, unassigned issues labeled `good first issue` / `beginner` / `easy` from 8 active Python AI repos (transformers, datasets, peft, langchain, llama_index, gradio, scikit-learn, keras).
- **Scores** them against my profile (Python, LLMs, NLP), how new they are, and how few comments they have.
- **Rechecks the top 15 live** right before sending, and drops anything that's closed, assigned, linked to a pull request, or claimed in the comments ("I'd like to work on this", "assign me", ...).
- **Explains** the top 5 with a local Gemma: a summary, a difficulty rating with the reason, what you'll learn, and 2–4 first steps.

Who gets to be lazier? Me, and any beginner who wants to contribute to AI open source but doesn't know where to start.

## Demo

[Add a link to a sample digest or a short video here once the scheduled run is live.]

## Code

{% github HarshadaGirase/FirstPick %}

## How I Built It

- **Model:** Gemma 3 4B (`gemma3:4b`), running locally through **Ollama**. No API key, no cloud LLM.
- **Language:** plain Python 3.11 with only `requests`, `PyYAML` and `pytest`. No frameworks, so a beginner can read every file.
- **GitHub REST API** for search, issue timelines (to spot linked PRs) and comments (to spot claims).

The model is treated as **untrusted**, and so is the issue text it reads:

- The issue body goes inside `<issue>` tags, and the system prompt says it's data, not instructions. Issue text can't close that tag early.
- HTML comments and images are stripped before the model sees anything.
- Ollama is called with a **JSON schema**, and every answer is checked again in Python: required fields, length limits, and a difficulty that must be `easy`, `medium` or `tricky`.
- **Hallucination guard:** any file path, URL or function name in the answer must appear in the original issue, or the answer is rejected. The model gets one retry that tells it what was wrong. After that, the issue falls back to its title plus "explanation unavailable".
- **Safe output:** all issue and model text is HTML-escaped, and `@username` / `#123` are wrapped in backticks, so the digest never pings maintainers or adds noise to their issues.

The project has an offline test suite (35 tests, using saved JSON responses) for the recheck rules, sent-issue deduplication, escaping, and model-output validation, including the retry and fallback paths.

Still in progress: a scheduled **GitHub Actions** workflow that installs Ollama on the runner, pulls Gemma, and posts a digest once a day, plus an eval script that measures JSON validity, difficulty agreement, and resistance to prompt injection.

## Why Does Open Innovation Matter?

FirstPick reads untrusted text from thousands of strangers' issues every day. With an open-weight model running locally:

- **It costs nothing to run.** There's no API bill and no key to leak. It's designed to run on free GitHub Actions minutes.
- **Anyone can fork it** and run it for their own profile without signing up for anything.
- **I can see and control everything:** the model version, the temperature, the JSON schema. Nothing changes under me, and no issue data leaves the machine.

A closed API would have meant a paid key, a secret in CI, and a reason for other beginners not to fork it.

## My Agent Session

[Optional: link or embed your agent session here, or remove this section.]

## Prize Categories

[List the categories you're entering, or remove this section.]

---

*Inspired by [devto-digest](https://github.com/) by Thomas Bonnet.* [Replace with the real devto-digest link.]
