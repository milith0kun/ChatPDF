"""
ChatPDF Backend - FastAPI Application
Sistema de Chatbot Inteligente para Análisis de Documentos PDF Académicos
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import session, documents, chat
from app.db.redis_client import redis_manager
from app.db.qdrant_client import qdrant_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    # Startup - graceful connection (don't fail if services unavailable)
    try:
        await redis_manager.connect()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"⚠️ Redis not available: {e}")
    
    try:
        await qdrant_manager.connect()
        print("✅ Connected to Qdrant")
    except Exception as e:
        print(f"⚠️ Qdrant not available: {e}")
    
    print("🚀 ChatPDF API started successfully")
    
    yield
    
    # Shutdown
    try:
        await redis_manager.disconnect()
        await qdrant_manager.disconnect()
    except:
        pass
    print("👋 ChatPDF API shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="ChatPDF API",
    description="API para análisis inteligente de documentos PDF académicos usando RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(session.router, prefix="/api/session", tags=["Session"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ChatPDF API",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check with service status."""
    redis_status = await redis_manager.ping()
    qdrant_status = await qdrant_manager.ping()
    
    return {
        "status": "healthy" if (redis_status and qdrant_status) else "degraded",
        "services": {
            "redis": "connected" if redis_status else "disconnected",
            "qdrant": "connected" if qdrant_status else "disconnected"
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )
