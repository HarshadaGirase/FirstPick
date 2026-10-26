"""Ask a local Gemma (via Ollama) to explain an issue, and validate the answer."""

import json
import re
import time

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
PROMPT_PATH = "prompts/explain.txt"
DIFFICULTIES = ["easy", "medium", "tricky"]
MAX_LEN = {"summary": 300, "difficulty_reason": 200, "you_will_learn": 200}
STEP_MAX_LEN = 150
MIN_STEPS, MAX_STEPS = 2, 4

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "maxLength": MAX_LEN["summary"]},
        "difficulty": {"type": "string", "enum": DIFFICULTIES},
        "difficulty_reason": {"type": "string", "maxLength": MAX_LEN["difficulty_reason"]},
        "you_will_learn": {"type": "string", "maxLength": MAX_LEN["you_will_learn"]},
        "first_steps": {
            "type": "array",
            "items": {"type": "string", "maxLength": STEP_MAX_LEN},
            "minItems": MIN_STEPS,
            "maxItems": MAX_STEPS,
        },
    },
    "required": ["summary", "difficulty", "difficulty_reason", "you_will_learn", "first_steps"],
    "additionalProperties": False,
}

# Things in the model's answer that must also appear in the issue text.
URL_RE = re.compile(r"https?://[^\s)\]>\"'`]+")
PATH_RE = re.compile(r"[\w.-]*/[\w./-]+")
DOTTED_RE = re.compile(r"\b[A-Za-z_]\w+(?:\.[A-Za-z_]\w+)+\b")  # config.py, torch.nn.Linear
SNAKE_RE = re.compile(r"\b[A-Za-z]\w*_\w+\b")                     # get_peft_model
CALL_RE = re.compile(r"\b[A-Za-z_]\w*(?=\()")                     # load_adapter(
BACKTICK_RE = re.compile(r"`([^`]+)`")
TRAILING = ".,;:!?/"


def clean_text(text):
    """Remove HTML comments and images (markdown and <img>) from issue text."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()


def load_prompt(path=PROMPT_PATH):
    """Return (system_prompt, user_template) from prompts/explain.txt."""
    with open(path, encoding="utf-8") as f:
        system, user = f.read().split("\n---\n", 1)
    return system.strip(), user.strip()


def build_user_message(template, issue, level):
    def neutral(text):
        # Stop issue text from closing our <issue> tag early.
        return re.sub(r"</?issue>", "[issue]", text, flags=re.IGNORECASE)

    values = {
        "repo": issue["repo"],
        "level": level,
        "title": neutral(issue["title"]),
        "body": neutral(clean_text(issue["body"])),
    }
    # One pass, so placeholders inside the issue text are never substituted.
    return re.sub(r"\{(repo|level|title|body)\}", lambda m: values[m.group(1)], template)


def mentioned_identifiers(text):
    """File paths, URLs and code identifiers mentioned in text."""
    found = set(URL_RE.findall(text))
    rest = URL_RE.sub(" ", text)
    for match in PATH_RE.findall(rest):
        match = match.rstrip(TRAILING)
        if match.count("/") >= 2 or re.search(r"\.\w{1,5}$", match):
            found.add(match)
            rest = rest.replace(match, " ")  # don't also report pieces of the path
    for regex in (DOTTED_RE, SNAKE_RE, CALL_RE, BACKTICK_RE):
        found.update(m.strip().rstrip(TRAILING) for m in regex.findall(rest))
    return {f for f in found if f}


def validate(result, source_text):
    """Return a list of problems with the model's answer (empty list = valid)."""
    if not isinstance(result, dict):
        return ["answer is not a JSON object"]
    errors = []
    expected = set(SCHEMA["required"])
    if set(result) != expected:
        errors.append(f"keys must be exactly {sorted(expected)}, got {sorted(result)}")
        return errors

    for key, limit in MAX_LEN.items():
        if not isinstance(result[key], str) or not result[key].strip():
            errors.append(f"{key} must be a non-empty string")
        elif len(result[key]) > limit:
            errors.append(f"{key} is longer than {limit} characters")

    if result["difficulty"] not in DIFFICULTIES:
        errors.append(f"difficulty must be one of {DIFFICULTIES}, got {result['difficulty']!r}")

    steps = result["first_steps"]
    if not isinstance(steps, list) or not MIN_STEPS <= len(steps) <= MAX_STEPS:
        errors.append(f"first_steps must be a list of {MIN_STEPS}-{MAX_STEPS} items")
    else:
        for step in steps:
            if not isinstance(step, str) or not step.strip():
                errors.append("each first step must be a non-empty string")
            elif len(step) > STEP_MAX_LEN:
                errors.append(f"a first step is longer than {STEP_MAX_LEN} characters")

    if errors:
        return errors

    answer_text = "\n".join([result["summary"], result["difficulty_reason"], result["you_will_learn"], *steps])
    source_lower = source_text.lower()
    for ident in sorted(mentioned_identifiers(answer_text)):
        if ident.lower() not in source_lower:
            errors.append(f"mentions {ident!r}, which is not in the issue")
    return errors


def call_ollama(model, messages):
    """Send one chat request to Ollama and return the reply text."""
    response = requests.post(OLLAMA_URL, json={
        "model": model,
        "messages": messages,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0.2},
    }, timeout=300)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama {OLLAMA_URL} -> {response.status_code}: {response.text[:500]}")
    return response.json()["message"]["content"]


def fallback(issue):
    return {
        "summary": issue["title"],
        "difficulty": "unknown",
        "difficulty_reason": "explanation unavailable",
        "you_will_learn": "explanation unavailable",
        "first_steps": [],
    }


def explain(issue, model, level):
    """Explain one issue. Tries twice, then falls back.

    Returns a dict: explanation, fallback (bool), first_try_valid (bool),
    attempts, seconds (total model time), errors (from the last attempt).
    """
    system, template = load_prompt()
    user = build_user_message(template, issue, level)
    source_text = "\n".join([issue["repo"], issue["title"], clean_text(issue["body"])])
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    seconds = 0.0
    errors = []
    for attempt in (1, 2):
        start = time.monotonic()
        reply = call_ollama(model, messages)
        seconds += time.monotonic() - start
        try:
            result = json.loads(reply)
        except json.JSONDecodeError as e:
            result, errors = None, [f"reply is not valid JSON: {e}"]
        else:
            errors = validate(result, source_text)
        if not errors:
            return {"explanation": result, "fallback": False, "first_try_valid": attempt == 1,
                    "attempts": attempt, "seconds": round(seconds, 2), "errors": []}
        # Retry once, telling the model what was wrong.
        messages = messages + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": "Your answer was rejected: " + "; ".join(errors)
                                        + ". Return corrected JSON only."},
        ]

    return {"explanation": fallback(issue), "fallback": True, "first_try_valid": False,
            "attempts": 2, "seconds": round(seconds, 2), "errors": errors}
