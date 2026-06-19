"""FastAPI 服务器 - 提供前端静态文件和聊天API（支持流式输出）"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

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
FRONTEND_DIR = Path(__file__).parent / "frontend"
KNOWLEDGE_DIR = Path(__file__).parent / "data" / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    message: str
    stream: bool = True
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


async def generate_stream(message: str, session_id: str):
    """生成流式响应"""
    global orchestrator
    
    try:
        result = await orchestrator.run(message)
        content = result.summary.content
        
        knowledge_sources = []
        if result.knowledge.chunks:
            for chunk in result.knowledge.chunks[:3]:
                if chunk.source:
                    knowledge_sources.append(chunk.source)
        
        chunk_size = 10
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
            await asyncio.sleep(0.02)
        
        yield f"data: {json.dumps({'content': '', 'done': True, 'metadata': {'intent': result.intent.intent_type.value, 'confidence': result.intent.confidence, 'knowledge_used': len(result.knowledge.chunks) > 0, 'knowledge_sources': knowledge_sources}})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    if request.stream:
        return StreamingResponse(
            generate_stream(request.message, request.session_id),
            media_type="text/event-stream"
        )
    
    try:
        result = await orchestrator.run(request.message)
        
        knowledge_sources = []
        if result.knowledge.chunks:
            for chunk in result.knowledge.chunks[:3]:
                if chunk.source:
                    knowledge_sources.append(chunk.source)
        
        return ChatResponse(
            response=result.summary.content,
            session_id=request.session_id,
            metadata={
                "intent": result.intent.intent_type.value,
                "confidence": result.intent.confidence,
                "elapsed_ms": result.elapsed_ms,
                "knowledge_used": len(result.knowledge.chunks) > 0,
                "knowledge_sources": knowledge_sources,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    """上传知识库文件"""
    try:
        content = await file.read()
        text = content.decode("utf-8")
        
        file_path = KNOWLEDGE_DIR / file.filename
        file_path.write_text(text, encoding="utf-8")
        
        if orchestrator:
            await orchestrator.knowledge_retriever.add_document(
                text,
                metadata={"source": file.filename, "type": "user_upload"}
            )
        
        return {"status": "success", "filename": file.filename, "size": len(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/list")
async def list_knowledge():
    """列出知识库文件"""
    files = []
    for f in KNOWLEDGE_DIR.glob("*"):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime
            })
    return {"files": files}


@app.get("/api/knowledge/status")
async def knowledge_status():
    """获取知识库状态"""
    files = list(KNOWLEDGE_DIR.glob("*"))
    file_count = len([f for f in files if f.is_file()])
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    
    return {
        "file_count": file_count,
        "total_size": total_size,
        "total_size_kb": round(total_size / 1024, 2),
        "embedding_available": orchestrator.knowledge_retriever._vector_store is not None if orchestrator else False
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    index_path = FRONTEND_DIR / "index.html"
    return FileResponse(index_path)


@app.get("/{path:path}")
async def serve_frontend(path: str):
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    index_path = FRONTEND_DIR / "index.html"
    return FileResponse(index_path)


if __name__ == "__main__":
    import uvicorn
    print("启动 AI Advisor Agent 服务器...")
    print("访问 http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
