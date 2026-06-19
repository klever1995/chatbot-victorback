from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# ==================== BASE ====================
class DocumentoBase(BaseModel):
    nombre: str = Field(..., max_length=255, description="Nombre original del archivo")
    activo: Optional[bool] = True
    carpeta_id: Optional[int] = None

# ==================== CREATE ====================
class DocumentoCreate(DocumentoBase):
    usuario_id: int
    nombre_almacenado: str = Field(..., max_length=255)
    ruta: str = Field(..., max_length=500)
    tamano_bytes: Optional[int] = None
    tipo_mime: Optional[str] = Field(None, max_length=100)
    extension: Optional[str] = Field(None, max_length=20)

# ==================== UPDATE ====================
class DocumentoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = None
    carpeta_id: Optional[int] = None

# ==================== RESPONSE ====================
class DocumentoResponse(DocumentoBase):
    id: int
    nombre_almacenado: str
    ruta: str
    tamano_bytes: Optional[int] = None
    tipo_mime: Optional[str] = None
    extension: Optional[str] = None
    usuario_id: int
    fecha_subida: datetime
    fecha_actualizacion: Optional[datetime] = None
    ultimo_acceso: Optional[datetime] = None
    # Relaciones (opcional, puedes incluirlas si necesitas mostrar datos anidados)
    # carpeta: Optional['CarpetaResponse'] = None
    # usuario: Optional['UsuarioResponse'] = None

    class Config:
        from_attributes = True

# ==================== LISTA ====================
class DocumentoListResponse(BaseModel):
    id: int
    nombre: str
    activo: bool
    carpeta_id: Optional[int]
    fecha_subida: datetime
    tamano_bytes: Optional[int] = None
    tipo_mime: Optional[str] = None
    extension: Optional[str] = None

    class Config:
        from_attributes = True

# ==================== ACTIVAR/DESACTIVAR ====================
class DocumentoToggleActivo(BaseModel):
    activo: bool