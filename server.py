"""FastAPI 服务器 - 提供前端静态文件和聊天API"""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator import Orchestrator
from src.utils.config import load_config

app = FastAPI(title="AI Advisor Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator: Optional[Orchestrator] = None


class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    session_id: str = "default"
    metadata: dict = {}


@app.on_event("startup")
async def startup_event():
    global orchestrator
    load_config()
    orchestrator = Orchestrator()


@app.get("/")
async def root():
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    return FileResponse(frontend_path)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    try:
        result = await orchestrator.run(request.message)
        
        return ChatResponse(
            response=result.summary.content,
            session_id=request.session_id,
            metadata={
                "intent": result.intent.intent_type.value,
                "confidence": result.intent.confidence,
                "elapsed_ms": result.elapsed_ms,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


frontend_path = Path(__file__).parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
