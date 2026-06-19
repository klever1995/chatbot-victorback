from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# ==================== BASE ====================
class ChunkBase(BaseModel):
    texto: str
    indice: int

# ==================== RESPONSE ====================
class ChunkResponse(ChunkBase):
    id: int
    documento_id: int
    fecha_creacion: datetime

    class Config:
        from_attributes = True

# ==================== RESULTADO DE BÚSQUEDA ====================
class ChunkSearchResult(ChunkResponse):
    similitud: float  # Score de similitud (0 a 1) del embedding vs consulta
    documento_nombre: Optional[str] = None  # Para mostrar de qué documento viene

    class Config:
        from_attributes = True

# ==================== CHUNK CON DOCUMENTO (para contexto) ====================
class ChunkWithDocumentResponse(ChunkResponse):
    documento_nombre: str
    documento_activo: bool

    class Config:
        from_attributes = True

# ==================== LISTA ====================
class ChunkListResponse(BaseModel):
    id: int
    indice: int
    texto_preview: str  # Primeros 100 caracteres del texto
    documento_id: int
    fecha_creacion: datetime

    class Config:
        from_attributes = True