from fastapi import FastAPI
from app.routers import company_core
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from fastapi.responses import FileResponse
import os

app = FastAPI()


app.include_router(company_core.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/share/{share_id}")
async def shared_page(share_id: str):
    file_path = os.path.join("static", "share.html")
    return FileResponse(file_path)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    