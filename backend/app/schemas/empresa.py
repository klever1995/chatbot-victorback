from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class EmpresaBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    activa: Optional[bool] = True

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaResponse(EmpresaBase):
    id: int
    fecha_registro: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    activa: Optional[bool] = None