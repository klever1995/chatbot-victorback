from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import engine, Base
from app.api.v1.endpoints import empresas as empresas_router
from app.api.v1.endpoints import usuarios as usuarios_router
from app.api.v1.endpoints import auth as auth_router
from app.api.v1.endpoints import documento as documento_router
from app.api.v1.endpoints import carpeta as carpeta_router
from app.api.v1.endpoints import chat as chat_router  # 👈 NUEVO IMPORT
from app.models import Empresa, Usuario, VerificacionToken, Documento, Carpeta, Chunk

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Knowledge Bot API - Sistema RAG con pgvector",
    description="API para gestión de documentos, carpetas y conversaciones con búsqueda semántica",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ROUTERS ====================
# Rutas de autenticación y usuarios
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(usuarios_router.router, prefix="/api/v1")
app.include_router(empresas_router.router, prefix="/api/v1")

# Rutas de gestión de conocimiento (RAG)
app.include_router(documento_router.router, prefix="/api/v1")
app.include_router(carpeta_router.router, prefix="/api/v1")

# 👈 NUEVO ROUTER DE CHAT
app.include_router(chat_router.router, prefix="/api/v1")

# ==================== ENDPOINTS PÚBLICOS ====================
@app.get("/")
def read_root():
    return {
        "message": "Knowledge Bot API funcionando correctamente",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Servidor activo"}