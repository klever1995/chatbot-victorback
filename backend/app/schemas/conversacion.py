from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

# ==================== MENSAJES ====================
class MensajeBase(BaseModel):
    texto: str = Field(..., min_length=1, description="Contenido del mensaje")
    rol: str = Field(..., pattern="^(usuario|asistente)$", description="usuario o asistente")

class MensajeCreate(BaseModel):
    texto: str = Field(..., min_length=1, description="Contenido del mensaje")
    rol: Optional[str] = "usuario"  # Por defecto es usuario, el backend asigna 'asistente' para respuestas

class MensajeResponse(BaseModel):
    id: int
    conversacion_id: int
    rol: str
    texto: str
    fuentes: Optional[str] = None  # JSON con las fuentes usadas
    fecha: datetime

    class Config:
        from_attributes = True

# ==================== CONVERSACIONES ====================
class ConversacionBase(BaseModel):
    titulo: Optional[str] = Field(None, max_length=255, description="Título de la conversación")
    activa: Optional[bool] = True

class ConversacionCreate(ConversacionBase):
    usuario_id: int  # El backend lo asigna desde el token

class ConversacionResponse(ConversacionBase):
    id: int
    usuario_id: int
    fecha_inicio: datetime
    fecha_actualizacion: Optional[datetime] = None
    ultimo_mensaje: Optional[datetime] = None
    mensajes_count: Optional[int] = 0  # Contador de mensajes (útil para UI)

    class Config:
        from_attributes = True

class ConversacionDetailResponse(ConversacionResponse):
    mensajes: List[MensajeResponse] = []  # Lista completa de mensajes de la conversación

    class Config:
        from_attributes = True

# ==================== ACTUALIZAR ====================
class ConversacionUpdate(BaseModel):
    titulo: Optional[str] = Field(None, max_length=255)
    activa: Optional[bool] = None

# ==================== LISTA ====================
class ConversacionListResponse(BaseModel):
    id: int
    titulo: Optional[str]
    activa: bool
    fecha_inicio: datetime
    ultimo_mensaje: Optional[datetime]
    mensajes_count: int

    class Config:
        from_attributes = True