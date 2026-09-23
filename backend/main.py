import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from . import claid, jobs, llm, profile  # noqa: E402

SHIRT_PROMPT = (
    "Convert this flat shirt illustration into a highly realistic product photo while preserving the exact design, "
    "color, logo, pocket placement, collar, sleeves, buttons, and proportions. Keep the shirt front-facing and centered "
    "with realistic fabric texture, natural folds, stitching details, and soft studio lighting. Use a clean light "
    "neutral background and make it look like a premium e-commerce clothing photo. Do not redesign, modify, or add "
    "extra objects, people, mannequins, or accessories. Make the background in White Color. The shot seem to appear "
    "that it has been taken on a ghost mannequin."
)
PANT_PROMPT = (
    "create a realistic photo of school uniform trousers for {kids}. Flatlay composition, shot from above, resting on a "
    "white background. Soft, even natural light, gentle shadows, clean modern e-commerce aesthetic."
)
MODEL_POSE = (
    "full body photo of {child} with body proportions and height natural for that age, standing confidently facing "
    "the camera, wearing the complete school uniform. Wearing polished black school shoes with shoelaces and short "
    "white socks. A school bag is on {his} shoulder. Uniform displayed very clearly, professional e-commerce product "
    "photography"
)
MODEL_BACKGROUND = "well-lit white background, clean professional studio lighting, bright and clear"
VIDEO_PROMPT = (
    "A realistic video of {child} wearing a clear, fully visible school uniform, standing centered in a softly lit "
    "neutral studio background. {He} takes 3-4 slow natural steps forward like arriving at school while keeping {his} "
    "face visible and looking toward the camera with a warm playful smile, moving the way a child of that age "
    "naturally moves. {He} lightly adjusts one backpack strap as the bag gently swings. {His} shirt, collar, sleeves, "
    "socks, and black school shoes move naturally with realistic fabric motion. The camera stays locked on a tripod "
    "with stable full-body framing, no zoom, no crop, no camera movement. The child remains centered and fully "
    "visible for the entire {seconds} second video, with consistent facial features and no distortion or disappearance."
)
VIDEO_NEGATIVE = (
    "blurry motion, distorted body, extra limbs, flickering, shaky camera, unrealistic movement, warped face, low quality"
)

app = FastAPI(title="Uniforma")


class Character(BaseModel):
    age: int = 8
    gender: str = "boy"


def _fill(template: str, c: Character, seconds: int = 5) -> str:
    girl = c.gender == "girl"
    return template.format(
        child=profile.describe(c.age, c.gender),
        he="she" if girl else "he", He="She" if girl else "He",
        his="her" if girl else "his", His="Her" if girl else "His",
        seconds=seconds,
    )


def _job(factory) -> dict:
    """Start background work and hand the browser a job id to poll."""
    return {"jobId": jobs.start(factory)}


@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown or expired job")
    return job


# 1) uniforma-upload: flat illustrations -> realistic product photos
@app.post("/api/upload")
async def upload(shirt: UploadFile = File(...), pant: UploadFile | None = File(None)):
    async def realistic(f: tuple, prompt: str) -> str:
        content, filename, content_type = f
        url = await claid.upload_image(content, filename, content_type)
        return await claid.ai_edit(url, prompt)

    has_pant = pant is not None and bool(pant.filename)
    character = profile.guess(shirt.filename, pant.filename if has_pant else None)
    # read the uploads now: the request body is gone once we answer
    shirt_file = (await shirt.read(), shirt.filename, shirt.content_type)
    pant_file = (await pant.read(), pant.filename, pant.content_type) if has_pant else None

    async def work() -> dict:
        tasks = [realistic(shirt_file, SHIRT_PROMPT)]
        if pant_file:
            kids = "girls" if character["gender"] == "girl" else "boys"
            tasks.append(realistic(pant_file, PANT_PROMPT.format(kids=kids)))
        results = await asyncio.gather(*tasks)
        return {
            "shirtUrl": results[0],
            "pantUrl": results[1] if len(results) > 1 else None,
            "character": character,
        }

    return _job(work)


# 2) uniforma-improve: feedback -> improved shirt / pant
class ImproveBody(BaseModel):
    shirtUrl: str
    pantUrl: str | None = None
    feedback: str


@app.post("/api/improve")
def improve(body: ImproveBody):
    async def one(url: str | None, make_prompt) -> str | None:
        if not url:
            return None
        prompt = await make_prompt(body.feedback)
        if llm.is_skip(prompt):
            return url  # feedback didn't concern this garment
        return await claid.ai_edit(url, prompt)

    async def work() -> dict:
        shirt, pant = await asyncio.gather(
            one(body.shirtUrl, llm.shirt_prompt),
            one(body.pantUrl, llm.pant_prompt),
        )
        return {"shirtUrl": shirt, "pantUrl": pant}

    return _job(work)


# 3) for-model-generation: child wearing the uniform
class ModelBody(BaseModel):
    shirtUrl: str
    pantUrl: str | None = None
    character: Character = Character()


@app.post("/api/model")
def model(body: ModelBody):
    clothing = [u for u in (body.shirtUrl, body.pantUrl) if u]
    pose = _fill(MODEL_POSE, body.character)

    async def work() -> dict:
        url = await claid.fashion_model(clothing, pose, MODEL_BACKGROUND)
        return {"modelUrl": url}

    return _job(work)


# 4) edit-model-image
class EditModelBody(BaseModel):
    modelUrl: str
    instruction: str


@app.post("/api/edit-model")
def edit_model(body: EditModelBody):
    async def work() -> dict:
        prompt = await llm.model_edit_prompt(body.instruction)
        url = await claid.ai_edit(body.modelUrl, prompt, model="v2", aspect_ratio=None)
        return {"modelUrl": url}

    return _job(work)


# 5) for-video-generation
class VideoBody(BaseModel):
    modelUrl: str
    character: Character = Character()
    instruction: str | None = None  # optional change, e.g. "make him wave at the camera"
    duration: int = 5               # Claid supports 5 or 10 seconds


@app.post("/api/video")
def video(body: VideoBody):
    duration = 10 if body.duration == 10 else 5
    base = _fill(VIDEO_PROMPT, body.character, duration)

    async def work() -> dict:
        prompt = base
        if body.instruction and body.instruction.strip():
            prompt = await llm.video_prompt(prompt, body.instruction.strip())
        url = await claid.image_to_video(body.modelUrl, prompt, VIDEO_NEGATIVE, duration)
        return {"videoUrl": url, "prompt": prompt, "duration": duration}

    return _job(work)


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")
