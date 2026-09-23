import asyncio
import json
import os

import httpx

BASE = "https://api.claid.ai/v1"
TIMEOUT = httpx.Timeout(60.0)


class ClaidError(Exception):
    pass


def _headers() -> dict:
    key = os.getenv("CLAID_API", "").strip()
    if not key:
        raise RuntimeError("CLAID_API is missing in .env")
    return {"Authorization": f"Bearer {key}"}


async def upload_image(content: bytes, filename: str, content_type: str | None) -> str:
    """Upload a local file to Claid and get a public tmp_url.
    Replaces the Google Drive + UploadToURL nodes from n8n."""
    data = {"operations": {}, "output": {"format": "png"}}
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post(
            f"{BASE}/image/edit/upload",
            headers=_headers(),
            files={"file": (filename, content, content_type or "image/png")},
            data={"data": json.dumps(data)},
        )
    if r.status_code >= 400:
        raise ClaidError(f"Upload failed: {r.text}")
    return r.json()["data"]["output"]["tmp_url"]


# Claid allows ~1 generation per second, so space out starts and retry on 429.
_START_GAP = 1.2
_start_lock = asyncio.Lock()
_last_start = 0.0


async def _start(path: str, payload: dict, retries: int = 5) -> int:
    global _last_start
    loop = asyncio.get_running_loop()
    for attempt in range(retries + 1):
        async with _start_lock:
            wait = _last_start + _START_GAP - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            _last_start = loop.time()
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(f"{BASE}/{path}", headers=_headers(), json=payload)
        if r.status_code == 429 and attempt < retries:
            await asyncio.sleep(float(r.headers.get("Retry-After") or 2 * (attempt + 1)))
            continue
        if r.status_code >= 400:
            raise ClaidError(f"{path} failed: {r.text}")
        return r.json()["data"]["id"]
    raise ClaidError(f"{path} failed: rate limited")


async def _poll(path: str, task_id: int, interval: float = 3, max_wait: float = 300) -> dict:
    """Poll until DONE (replaces the fixed Wait nodes)."""
    waited = 0.0
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        while waited < max_wait:
            r = await c.get(f"{BASE}/{path}/{task_id}", headers=_headers())
            if r.status_code == 429:
                await asyncio.sleep(interval)
                waited += interval
                continue
            if r.status_code >= 400:
                raise ClaidError(f"Polling {path} failed: {r.text}")
            data = r.json()["data"]
            status = data.get("status")
            if status == "DONE":
                return data["result"]
            if status in ("ERROR", "CANCELLED"):
                raise ClaidError(f"{path} task {task_id} ended with {status}: {data.get('errors')}")
            await asyncio.sleep(interval)
            waited += interval
    raise ClaidError(f"{path} task {task_id} timed out")


async def ai_edit(image_url: str, prompt: str, model: str = "v1", aspect_ratio: str | None = "3:4") -> str:
    options = {"prompt": prompt, "model": model, "inference_steps": 50, "guidance_scale": 7.5}
    if aspect_ratio:
        options["aspect_ratio"] = aspect_ratio
    task_id = await _start("image/ai-edit", {
        "input": image_url,
        "options": options,
        "output": {"number_of_images": 1, "format": "png"},
    })
    result = await _poll("image/ai-edit", task_id)
    return result["output_objects"][0]["tmp_url"]


async def fashion_model(clothing: list[str], pose: str, background: str) -> str:
    task_id = await _start("image/ai-fashion-models", {
        "input": {"clothing": clothing},
        "output": {"format": "png", "number_of_images": 1},
        "options": {"pose": pose, "background": background, "aspect_ratio": "3:4"},
    })
    result = await _poll("image/ai-fashion-models", task_id)
    return result["output_objects"][0]["tmp_url"]


async def image_to_video(image_url: str, prompt: str, negative_prompt: str, duration: int = 5) -> str:
    task_id = await _start("video/generate", {
        "input": image_url,
        "options": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": duration,
            "guidance_scale": 0.5,
        },
    })
    result = await _poll("video/generate", task_id, interval=5, max_wait=600)
    return result["output_object"]["tmp_url"]
