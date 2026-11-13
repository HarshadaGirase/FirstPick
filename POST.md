    *This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

    ## What I Built

    **FirstPick** finds beginner-friendly GitHub issues in open-source AI repos, drops the ones someone has already taken, and hands me the 5 best, explained in plain English by Gemma running on my own laptop.

    I wanted my first contribution to an AI library. Searching "good first issue" meant ten tabs, and most of them were closed, assigned, already had a pull request, or had a "can I work on this?" comment from weeks ago. FirstPick does that digging for me:

    - **Collects** open, unassigned issues labeled `good first issue` / `beginner` / `easy` from 8 active Python AI repos (transformers, datasets, peft, langchain, llama_index, gradio, scikit-learn, keras).
    - **Scores** them against my profile (Python, LLMs, NLP), how new they are, and how few comments they have.
    - **Re-checks the top 15 live** right before delivering, and drops anything closed, assigned, linked to a pull request, or claimed in the comments ("I'd like to work on this", "assign me", ...).
    - **Explains** the top 5 with a local Gemma: a summary, a difficulty rating with the reason, what you'd learn, and 2–4 first steps.

    Who gets to be lazier? Me, and any beginner who wants to contribute to AI open source but doesn't know where to start.

    ## Demo

    [[Screenshot: one explained card from preview.md]]

    Try it yourself. `dry-run` writes a local preview and posts nothing:

        git clone https://github.com/HarshadaGirase/FirstPick.git
        cd FirstPick
        pip install -r requirements.txt
        echo "GITHUB_TOKEN=<your token>" > .env
        ollama pull gemma3:4b
        python main.py collect
        python main.py dry-run
        python -m pytest

    ## Code

    {% github HarshadaGirase/FirstPick %}

    ## How I Built It

    - **Model:** Gemma 3 4B (`gemma3:4b`), running locally through **Ollama**. No API key, no cloud LLM.
    - **Language:** plain Python 3.11 with only `requests`, `PyYAML` and `pytest`. No frameworks, so a beginner can read every file.
    - **GitHub REST API** for search, issue timelines (to spot linked PRs) and comments (to spot claims).

    I treat the issue text as **untrusted**, and the model's answers too:

    - The issue body goes inside `<issue>` tags, and the system prompt says it's data, not instructions. Issue text can't close that tag early: any `<issue>` or `</issue>` inside it is replaced before the model sees it.
    - HTML comments and images are stripped before the model sees anything.
    - Ollama is called with a **JSON schema**, and every answer is checked again in Python: required fields, length limits, and a difficulty that must be `easy`, `medium` or `tricky`.
    - **Hallucination guard:** any file path, URL or function name in the answer must appear in the original issue, or the answer is rejected. The model gets one retry that says what was wrong; after that, the issue falls back to its title plus "explanation unavailable".
    - **No noise for maintainers:** all text is HTML-escaped, and `@username` / `#123` are wrapped in backticks, so the digest never pings anyone or adds a "mentioned this" to their issues.

    An offline test suite (35 tests, using saved JSON responses) covers the re-check rules, sent-issue deduplication, escaping, and model-output validation, including the retry and fallback paths.

    ## What Broke Along the Way

    - **GitHub's secondary rate limit.** My first real `collect` run died after about 10 seconds with `403: You have exceeded a secondary rate limit`. I already handled `Retry-After` and `X-RateLimit-Remaining`, but this response had neither header, so my code treated it as a real error and stopped. Now it recognises the message, waits 60 seconds (120 on the second try), and retries.
    - **A broken Ollama install hid behind a vague error.** Every model call returned `500 Internal Server Error`. Fetching Ollama's actual error showed the real cause: its `llama-server` binary was missing, so it couldn't run *any* model. I changed FirstPick to show Ollama's own error message instead of a bare 500, so the next person sees the cause straight away.
    - **My scoring counted "LLMs" twice.** To match both "LLM" and "LLMs", I searched for both, so any issue that said "LLMs" got two points for one interest. Now each profile word counts once.
    - **The hallucination guard over-reported.** A single made-up path like `src/peft/utils/fake_helpers.py` was reported three times: the path, then `fake_helpers.py` and `fake_helpers` found inside it. Now a path is removed from the text once it's matched, so each made-up name is reported once.

    ## Why Does Open Innovation Matter?

    FirstPick feeds text written by strangers to a model, every time it runs. With an open-weight model running locally:

    - **It costs nothing to run.** No API bill, no key to leak or store as a CI secret.
    - **Anyone can fork it** and run it for their own skills without signing up for anything.
    - **I control everything:** the model version, the temperature, the JSON schema. Nothing changes under me, and nothing is sent to a third-party AI service.

    A closed API would have meant a paid key, a secret to manage, and a reason for other beginners not to fork it.

    ## What's Next

    - A scheduled **GitHub Actions** workflow: collect every 6 hours, deliver every evening, with Gemma running on the runner.
    - An eval script measuring JSON validity, difficulty agreement with my own labels, and prompt-injection resistance.

    ## Prize Categories

    - **Best Use of Gemma:** Gemma 3 4B runs locally through Ollama and writes every explanation, constrained by a JSON schema and checked by a hallucination guard.

    *Inspired by [devto-digest](https://github.com/thomasbnt/your-devto-digest) by Thomas Bonnet: collecting candidates and re-checking them live before delivering.*
