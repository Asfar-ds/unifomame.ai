# Uniforma Studio

Turns a flat school-uniform illustration into a realistic product photo, a child model wearing
the uniform, and a short video.

## Run locally

1. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file in this folder:
   ```
   CLAID_API=your_claid_key
   GROQ_API=your_groq_key
   ```
3. Start the server:
   ```
   uvicorn backend.main:app --reload
   ```
4. Open http://localhost:8000

Opening `frontend/index.html` directly (Live Server and similar) will not work — the page needs
the backend to serve it.

## Deploy free on Render

1. Push this folder to a GitHub repository. `.env` is gitignored, so your keys stay local.
2. On Render: **New → Web Service**, pick the repository. `render.yaml` fills in the settings.
3. Under **Environment**, add `CLAID_API` and `GROQ_API`.
4. Deploy, then open the `.onrender.com` URL.

Free instances sleep after 15 minutes of inactivity, so the first request afterwards takes about
a minute. Long jobs run in the background and the page polls for the result, so a slow video does
not break the request.

## How it works

| Step | Endpoint | Claid API |
| --- | --- | --- |
| Illustration → product photo | `POST /api/upload` | `image/edit/upload`, `image/ai-edit` |
| Apply feedback | `POST /api/improve` | `image/ai-edit` |
| Child model | `POST /api/model` | `image/ai-fashion-models` |
| Edit the model image | `POST /api/edit-model` | `image/ai-edit` |
| Video (5 or 10 s) | `POST /api/video` | `video/generate` |
| Poll any of the above | `GET /api/job/{id}` | — |

Each `POST` returns a `jobId`; poll `/api/job/{id}` until its status is `done` or `error`.

The class written in an uploaded file name (`Class 5 boys shirt.png`, `nursery girl.jpg`) sets the
child's age and gender in the prompts; the page lets you correct the guess.

Notes:

- Result URLs from Claid expire after 24 hours. Download anything you want to keep.
- Generated videos always contain an audio track; it cannot be turned off.
- Every image and video costs Claid credits, and a deployed URL is public — share it carefully.
