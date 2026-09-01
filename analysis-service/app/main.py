from fastapi import FastAPI

from app.api.webhook import router as webhook_router
from app.api.repository import router as repository_router

app = FastAPI()

app.include_router(webhook_router)
app.include_router(repository_router)

@app.get("/")
async def root():
    return {"message": "Analysis Service is running"}