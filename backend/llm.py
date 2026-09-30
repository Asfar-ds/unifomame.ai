"""Replaces the Groq 'AI Agent' nodes. Without a Groq key the raw text is sent to Claid as-is."""
import logging
import os

import httpx

log = logging.getLogger("uniforma")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SHIRT_SYSTEM = """You are an expert AI prompt engineer. Extract only SHIRT-related instructions from the user feedback.
Rules:
1. Remove any mention of pants or trousers.
2. If only pants are mentioned, return the word "SKIP".
3. If the prompt is only about changing the background, explicitly state to change only the background and not change anything (color/texture) of the shirt. If the prompt is about the shirt, explicitly state to change only the shirt and not the background. State it strictly.
4. Output ONLY the raw descriptive paragraph. No markdown, no "Here is your prompt", no bold text."""

PANT_SYSTEM = """You are an expert AI prompt engineer. Extract only PANT-related instructions from the user feedback.
Rules:
1. Remove any mention of shirts or tops.
2. If only shirt is mentioned, return the word "SKIP".
3. If the prompt is only about changing the background, explicitly state to change only the background and not change anything (color/texture) of the pant. If the prompt is about the pant, explicitly state to change only the pant and not the background. State it strictly.
4. Output ONLY the raw descriptive paragraph. No markdown, no "Here is your prompt", no bold text."""

FEEDBACK_USER = (
    "This is the feedback PROMPT: {text}. Just give the prompt in output, nothing else, plain text in one "
    "paragraph, no markdown. My English is not so good, so enhance my prompt with good English and turn it "
    "into a prompt, unless it is SKIP."
)

MODEL_EDIT_SYSTEM = (
    "You will receive a prompt from the user. Keep the original prompt exactly as it is and only improve its "
    "formatting into a single clean, natural, well-structured paragraph without changing the meaning, intent, "
    "instructions, requirements or important details. Remove hyphens, underscores, pipes, quotation marks, bullet "
    "points, numbering, headings, labels, line breaks and special characters. Return only one plain paragraph "
    "and nothing else."
)


async def _chat(system: str, user: str) -> str | None:
    """Returns None if Groq is unavailable, so the caller falls back to the raw text."""
    key = (os.getenv("GROQ_API") or os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, json={
                "model": MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        log.exception("Groq call failed; using the original text")
        return None


async def shirt_prompt(feedback: str) -> str:
    return await _chat(SHIRT_SYSTEM, FEEDBACK_USER.format(text=feedback)) or feedback


async def pant_prompt(feedback: str) -> str:
    return await _chat(PANT_SYSTEM, FEEDBACK_USER.format(text=feedback)) or feedback


VIDEO_EDIT_SYSTEM = (
    "You rewrite video generation prompts. You are given a BASE prompt and a CHANGE requested by the user. Return the "
    "base prompt rewritten so the change is applied, keeping every other detail intact, especially the subject, the "
    "clothing, the framing and the camera stability rules. Keep the description of the child's age unchanged. Output "
    "one single plain paragraph of 3 to 5000 characters, no markdown, no lists, no headings, no commentary, and "
    "nothing before or after the paragraph."
)


async def video_prompt(base: str, instruction: str) -> str:
    out = await _chat(VIDEO_EDIT_SYSTEM, f"BASE PROMPT: {base}\n\nCHANGE: {instruction}")
    return out or f"{base} Additionally, {instruction}"


async def model_edit_prompt(instruction: str) -> str:
    return await _chat(MODEL_EDIT_SYSTEM, f"Here is the prompt: {instruction}\n\nOutput the prompt only") or instruction


def is_skip(text: str) -> bool:
    return text.strip().strip(".").upper() == "SKIP"
