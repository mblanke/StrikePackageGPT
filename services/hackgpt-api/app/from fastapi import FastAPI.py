from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://strikepackage-llm-router:8000")


@app.get("/")
async def root():
    return {"message": "Hello World"}