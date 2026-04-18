import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import acreate_client

from app.routes import entries


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.supabase = await acreate_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SECRET_KEY"),
    )
    yield


app = FastAPI(title="Lumen API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entries.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
