from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

# ==================== BASE ====================
class CarpetaBase(BaseModel):
    nombre: str = Field(..., max_length=100, description="Nombre de la carpeta")
    descripcion: Optional[str] = Field(None, max_length=255, description="Descripción opcional")
    activa: Optional[bool] = True
    padre_id: Optional[int] = Field(None, description="ID de la carpeta padre (NULL si es raíz)")

# ==================== CREATE ====================
class CarpetaCreate(CarpetaBase):
    pass  # ✅ El usuario_id se obtiene del token, no del body

# ==================== UPDATE ====================
class CarpetaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=255)
    activa: Optional[bool] = None
    padre_id: Optional[int] = Field(None, description="NULL para mover a raíz")

# ==================== RESPONSE ====================
class CarpetaResponse(CarpetaBase):
    id: int
    usuario_id: int
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    subcarpetas: Optional[List['CarpetaResponse']] = []
    documentos_count: Optional[int] = 0

    class Config:
        from_attributes = True

# ==================== LISTA ====================
class CarpetaListResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    activa: bool
    padre_id: Optional[int]
    fecha_creacion: datetime
    documentos_count: Optional[int] = 0
    subcarpetas_count: Optional[int] = 0

    class Config:
        from_attributes = True

# ==================== ESTRUCTURA JERÁRQUICA ====================
class CarpetaTreeResponse(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]
    activa: bool
    subcarpetas: List['CarpetaTreeResponse'] = []
    documentos: List['DocumentoSimpleResponse'] = []

    class Config:
        from_attributes = True

# ==================== DOCUMENTO SIMPLE ====================
class DocumentoSimpleResponse(BaseModel):
    id: int
    nombre: str
    activo: bool
    extension: Optional[str]
    tamano_bytes: Optional[int]

    class Config:
        from_attributes = True

# Reconstrucción para referencias circulares
CarpetaTreeResponse.model_rebuild()
CarpetaResponse.model_rebuild()