from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
import os

from research_and_analyst.api.routes import report_routes


app = FastAPI(title="Autonomous Report Generator UI")


# ---------- PATHS ----------

# src/research_and_analyst/api/main.py
APP_DIR = Path(__file__).resolve().parent

# project root
PROJECT_DIR = APP_DIR.parents[2]


STATIC_DIR = PROJECT_DIR / "static"

TEMPLATES_DIR = APP_DIR / "templates"


print("STATIC:", STATIC_DIR)
print("STATIC EXISTS:", STATIC_DIR.exists())

print("TEMPLATES:", TEMPLATES_DIR)
print("TEMPLATES EXISTS:", TEMPLATES_DIR.exists())


# ---------- STATIC ----------

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ---------- TEMPLATES ----------

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)

app.templates = templates


def basename_filter(path: str):
    return os.path.basename(path)

templates.env.filters["basename"] = basename_filter


# ---------- CORS ----------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- HEALTH ----------

@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ---------- ROUTES ----------

app.include_router(report_routes.router)