from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.base import get_db
from app.models.carpeta import Carpeta
from app.models.documento import Documento
from app.models.usuarios import Usuario
from app.schemas.carpeta import (
    CarpetaResponse,
    CarpetaCreate,
    CarpetaUpdate,
    CarpetaListResponse,
    CarpetaTreeResponse
)
from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user

router = APIRouter(prefix="/carpetas", tags=["carpetas"])

# ==================== CREAR CARPETA ====================
@router.post("/", response_model=CarpetaResponse, status_code=status.HTTP_201_CREATED)
def crear_carpeta(
    carpeta_data: CarpetaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)  # Solo admin puede crear carpetas
):
    """Crea una nueva carpeta (solo administradores)"""
    
    # Verificar que la carpeta padre existe (si se proporcionó)
    if carpeta_data.padre_id:
        carpeta_padre = db.query(Carpeta).filter(Carpeta.id == carpeta_data.padre_id).first()
        if not carpeta_padre:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carpeta padre no encontrada"
            )
        # Verificar que la carpeta padre pertenece al usuario
        if carpeta_padre.usuario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para crear subcarpetas en esta carpeta"
            )
    
    # Verificar que no exista otra carpeta con el mismo nombre en la misma ubicación
    carpeta_existente = db.query(Carpeta).filter(
        Carpeta.nombre == carpeta_data.nombre,
        Carpeta.padre_id == carpeta_data.padre_id,
        Carpeta.usuario_id == current_user.id
    ).first()
    
    if carpeta_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una carpeta con este nombre en esta ubicación"
        )
    
    # Crear carpeta
    nueva_carpeta = Carpeta(
        nombre=carpeta_data.nombre,
        descripcion=carpeta_data.descripcion,
        activa=carpeta_data.activa if carpeta_data.activa is not None else True,
        padre_id=carpeta_data.padre_id,
        usuario_id=current_user.id
    )
    
    db.add(nueva_carpeta)
    db.commit()
    db.refresh(nueva_carpeta)
    
    return nueva_carpeta

# ==================== LISTAR CARPETAS ====================
@router.get("/", response_model=List[CarpetaListResponse])
def listar_carpetas(
    skip: int = 0,
    limit: int = 100,
    padre_id: Optional[int] = None,
    solo_activas: bool = False,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Lista todas las carpetas (filtradas por padre y estado)"""
    query = db.query(Carpeta)
    
    # Filtrar por carpeta padre
    if padre_id is not None:
        query = query.filter(Carpeta.padre_id == padre_id)
    else:
        # Si no se especifica, mostrar carpetas raíz (padre_id = NULL)
        query = query.filter(Carpeta.padre_id.is_(None))
    
    # Filtrar solo activas si se solicita
    if solo_activas:
        query = query.filter(Carpeta.activa == True)
    
    # Si no es admin, solo ver sus carpetas
    if current_user.rol != "admin":
        query = query.filter(Carpeta.usuario_id == current_user.id)
    
    carpetas = query.offset(skip).limit(limit).all()
    
    # Agregar conteo de documentos y subcarpetas
    resultado = []
    for carpeta in carpetas:
        documentos_count = db.query(Documento).filter(
            Documento.carpeta_id == carpeta.id,
            Documento.activo == True
        ).count()
        
        subcarpetas_count = db.query(Carpeta).filter(
            Carpeta.padre_id == carpeta.id,
            Carpeta.activa == True
        ).count()
        
        # Convertir a dict y agregar conteos
        carpeta_dict = {
            "id": carpeta.id,
            "nombre": carpeta.nombre,
            "descripcion": carpeta.descripcion,
            "activa": carpeta.activa,
            "padre_id": carpeta.padre_id,
            "fecha_creacion": carpeta.fecha_creacion,
            "documentos_count": documentos_count,
            "subcarpetas_count": subcarpetas_count
        }
        resultado.append(carpeta_dict)
    
    return resultado

# ==================== OBTENER CARPETA ====================
@router.get("/{carpeta_id}", response_model=CarpetaResponse)
def obtener_carpeta(
    carpeta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene una carpeta por su ID incluyendo sus subcarpetas y documentos"""
    carpeta = db.query(Carpeta).filter(Carpeta.id == carpeta_id).first()
    
    if not carpeta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carpeta no encontrada"
        )
    
    # Verificar permisos
    if current_user.rol != "admin" and carpeta.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta carpeta"
        )
    
    # Obtener subcarpetas
    subcarpetas = db.query(Carpeta).filter(
        Carpeta.padre_id == carpeta_id,
        Carpeta.activa == True
    ).all()
    
    # Obtener documentos
    documentos = db.query(Documento).filter(
        Documento.carpeta_id == carpeta_id,
        Documento.activo == True
    ).all()
    
    # Construir respuesta con relaciones
    carpeta_dict = {
        "id": carpeta.id,
        "nombre": carpeta.nombre,
        "descripcion": carpeta.descripcion,
        "activa": carpeta.activa,
        "padre_id": carpeta.padre_id,
        "usuario_id": carpeta.usuario_id,
        "fecha_creacion": carpeta.fecha_creacion,
        "fecha_actualizacion": carpeta.fecha_actualizacion,
        "subcarpetas": subcarpetas,
        "documentos_count": len(documentos)
    }
    
    return carpeta_dict

# ==================== OBTENER ÁRBOL DE CARPETAS ====================
@router.get("/arbol", response_model=List[CarpetaTreeResponse])
def obtener_arbol_carpetas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene la estructura completa de carpetas en forma de árbol"""
    
    # Obtener carpetas raíz (padre_id = NULL)
    query = db.query(Carpeta).filter(
        Carpeta.padre_id.is_(None),
        Carpeta.activa == True
    )
    
    if current_user.rol != "admin":
        query = query.filter(Carpeta.usuario_id == current_user.id)
    
    carpetas_raiz = query.all()
    
    # Función recursiva para construir el árbol
    def construir_arbol(carpeta: Carpeta) -> dict:
        # Obtener subcarpetas
        subcarpetas = db.query(Carpeta).filter(
            Carpeta.padre_id == carpeta.id,
            Carpeta.activa == True
        ).all()
        
        # Obtener documentos
        documentos = db.query(Documento).filter(
            Documento.carpeta_id == carpeta.id,
            Documento.activo == True
        ).all()
        
        return {
            "id": carpeta.id,
            "nombre": carpeta.nombre,
            "descripcion": carpeta.descripcion,
            "activa": carpeta.activa,
            "subcarpetas": [construir_arbol(sub) for sub in subcarpetas],
            "documentos": [
                {
                    "id": doc.id,
                    "nombre": doc.nombre,
                    "activo": doc.activo,
                    "extension": doc.extension,
                    "tamano_bytes": doc.tamano_bytes
                }
                for doc in documentos
            ]
        }
    
    arbol = [construir_arbol(carpeta) for carpeta in carpetas_raiz]
    return arbol

# ==================== ACTUALIZAR CARPETA ====================
@router.put("/{carpeta_id}", response_model=CarpetaResponse)
def actualizar_carpeta(
    carpeta_id: int,
    carpeta_data: CarpetaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Actualiza una carpeta existente (solo administradores)"""
    
    carpeta = db.query(Carpeta).filter(Carpeta.id == carpeta_id).first()
    
    if not carpeta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carpeta no encontrada"
        )
    
    update_data = carpeta_data.model_dump(exclude_unset=True)
    
    # Verificar que la carpeta padre existe (si se está moviendo)
    if "padre_id" in update_data and update_data["padre_id"] is not None:
        # No permitir que una carpeta sea su propio padre
        if update_data["padre_id"] == carpeta_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una carpeta no puede ser su propio padre"
            )
        
        carpeta_padre = db.query(Carpeta).filter(Carpeta.id == update_data["padre_id"]).first()
        if not carpeta_padre:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carpeta padre no encontrada"
            )
        
        # Verificar que no se cree un ciclo
        if carpeta_padre.padre_id == carpeta_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede mover una carpeta a una subcarpeta de sí misma"
            )
    
    # Verificar que no exista otra carpeta con el mismo nombre en la nueva ubicación
    if "nombre" in update_data or "padre_id" in update_data:
        nuevo_padre_id = update_data.get("padre_id", carpeta.padre_id)
        nuevo_nombre = update_data.get("nombre", carpeta.nombre)
        
        carpeta_existente = db.query(Carpeta).filter(
            Carpeta.nombre == nuevo_nombre,
            Carpeta.padre_id == nuevo_padre_id,
            Carpeta.id != carpeta_id,
            Carpeta.usuario_id == current_user.id
        ).first()
        
        if carpeta_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una carpeta con este nombre en esta ubicación"
            )
    
    for field, value in update_data.items():
        setattr(carpeta, field, value)
    
    carpeta.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(carpeta)
    
    return carpeta

# ==================== ELIMINAR CARPETA ====================
@router.delete("/{carpeta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_carpeta(
    carpeta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Elimina una carpeta (solo si está vacía) - solo administradores"""
    
    carpeta = db.query(Carpeta).filter(Carpeta.id == carpeta_id).first()
    
    if not carpeta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carpeta no encontrada"
        )
    
    # Verificar si tiene subcarpetas
    subcarpetas = db.query(Carpeta).filter(Carpeta.padre_id == carpeta_id).count()
    if subcarpetas > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la carpeta porque tiene subcarpetas. Elimina primero las subcarpetas."
        )
    
    # Verificar si tiene documentos
    documentos = db.query(Documento).filter(Documento.carpeta_id == carpeta_id).count()
    if documentos > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la carpeta porque contiene documentos. Mueve o elimina los documentos primero."
        )
    
    db.delete(carpeta)
    db.commit()
    
    return None

# ==================== MOVER DOCUMENTOS A CARPETA ====================
@router.post("/{carpeta_id}/mover-documentos")
def mover_documentos_a_carpeta(
    carpeta_id: int,
    documento_ids: List[int],
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Mueve múltiples documentos a una carpeta (solo administradores)"""
    
    # Verificar que la carpeta existe
    carpeta = db.query(Carpeta).filter(Carpeta.id == carpeta_id).first()
    if not carpeta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carpeta no encontrada"
        )
    
    # Verificar que la carpeta pertenece al usuario
    if carpeta.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para mover documentos a esta carpeta"
        )
    
    # Mover los documentos
    documentos_movidos = 0
    for doc_id in documento_ids:
        documento = db.query(Documento).filter(Documento.id == doc_id).first()
        if documento and documento.usuario_id == current_user.id:
            documento.carpeta_id = carpeta_id
            documento.fecha_actualizacion = datetime.now()
            documentos_movidos += 1
    
    db.commit()
    
    return {
        "mensaje": f"{documentos_movidos} documentos movidos a la carpeta '{carpeta.nombre}'",
        "documentos_movidos": documentos_movidos
    }