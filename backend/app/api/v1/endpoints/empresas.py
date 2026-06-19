from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.models.empresa import Empresa as EmpresaModel
from app.schemas.empresa import EmpresaResponse, EmpresaCreate, EmpresaUpdate

router = APIRouter(prefix="/empresas", tags=["empresas"])

@router.post("/", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def crear_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    """Crea una nueva empresa (solo nombre y activa)"""
    
    nueva_empresa = EmpresaModel(
        nombre=empresa.nombre,
        activa=empresa.activa if empresa.activa is not None else True
    )
    
    db.add(nueva_empresa)
    db.commit()
    db.refresh(nueva_empresa)
    
    return nueva_empresa

@router.get("/", response_model=List[EmpresaResponse])
def listar_empresas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lista todas las empresas (solo para administradores)"""
    empresas = db.query(EmpresaModel).offset(skip).limit(limit).all()
    return empresas

@router.get("/{empresa_id}", response_model=EmpresaResponse)
def obtener_empresa(empresa_id: int, db: Session = Depends(get_db)):
    """Obtiene una empresa por su ID"""
    empresa = db.query(EmpresaModel).filter(EmpresaModel.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    return empresa

@router.put("/{empresa_id}", response_model=EmpresaResponse)
def actualizar_empresa(
    empresa_id: int, 
    empresa_data: EmpresaUpdate, 
    db: Session = Depends(get_db)
):
    """Actualiza los datos de una empresa existente"""
    empresa = db.query(EmpresaModel).filter(EmpresaModel.id == empresa_id).first()
    
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    update_data = empresa_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(empresa, field, value)
    
    db.commit()
    db.refresh(empresa)
    
    return empresa

@router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_empresa(
    empresa_id: int,
    db: Session = Depends(get_db)
):
    """Elimina una empresa (solo si no tiene usuarios asociados)"""
    empresa = db.query(EmpresaModel).filter(EmpresaModel.id == empresa_id).first()
    
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    # Verificar si tiene usuarios asociados
    if empresa.usuarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la empresa porque tiene usuarios asociados"
        )
    
    db.delete(empresa)
    db.commit()
    
    return None