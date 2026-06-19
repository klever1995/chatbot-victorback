from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import uuid
from datetime import datetime
import magic

from app.db.base import get_db
from app.models.documento import Documento
from app.models.carpeta import Carpeta
from app.models.usuarios import Usuario
from app.schemas.documento import (
    DocumentoResponse, 
    DocumentoCreate, 
    DocumentoUpdate,
    DocumentoListResponse,
    DocumentoToggleActivo
)
from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.services.rag import RAGService

router = APIRouter(prefix="/documentos", tags=["documentos"])

# Configuración de almacenamiento
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/documentos")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== SUBIR DOCUMENTO ====================
@router.post("/subir", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def subir_documento(
    archivo: UploadFile = File(...),
    carpeta_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)  # Solo admin puede subir
):
    """Sube un nuevo documento (solo administradores)"""
    
    # Validar tipo de archivo
    tipos_permitidos = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]
    
    # Leer contenido para validar
    contenido = await archivo.read()
    
    # Detectar tipo MIME con magic
    tipo_mime = magic.from_buffer(contenido, mime=True)
    if tipo_mime not in tipos_permitidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no soportado. Permitidos: {', '.join(tipos_permitidos)}"
        )
    
    # Validar tamaño (ej: 50MB máximo)
    if len(contenido) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo excede el tamaño máximo permitido (50MB)"
        )
    
    # Verificar que la carpeta existe (si se proporcionó)
    if carpeta_id:
        carpeta = db.query(Carpeta).filter(Carpeta.id == carpeta_id).first()
        if not carpeta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carpeta no encontrada"
            )
        # Verificar que la carpeta pertenece al usuario (o es del admin)
        if carpeta.usuario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para subir a esta carpeta"
            )
    
    # Generar nombre único para el archivo
    extension = os.path.splitext(archivo.filename)[1]
    nombre_almacenado = f"{uuid.uuid4().hex}{extension}"
    ruta_completa = os.path.join(UPLOAD_DIR, nombre_almacenado)
    
    # Guardar archivo físicamente
    with open(ruta_completa, "wb") as f:
        f.write(contenido)
    
    # Crear registro en la base de datos
    documento = Documento(
        nombre=archivo.filename,
        nombre_almacenado=nombre_almacenado,
        ruta=ruta_completa,
        tamano_bytes=len(contenido),
        tipo_mime=tipo_mime,
        extension=extension,
        activo=True,
        usuario_id=current_user.id,
        carpeta_id=carpeta_id
    )
    
    db.add(documento)
    db.commit()
    db.refresh(documento)
    
    # Procesar el documento con RAG (extraer texto, chunking, embeddings)
    try:
        rag_service = RAGService(db)
        rag_service.procesar_documento(documento.id, contenido, tipo_mime)
    except Exception as e:
        # Si falla el procesamiento, eliminar el documento y el archivo
        os.remove(ruta_completa)
        db.delete(documento)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el documento: {str(e)}"
        )
    
    return documento

# ==================== LISTAR DOCUMENTOS ====================
@router.get("/", response_model=List[DocumentoListResponse])
def listar_documentos(
    skip: int = 0,
    limit: int = 100,
    carpeta_id: Optional[int] = None,
    solo_activos: bool = False,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Lista todos los documentos (filtrados por carpeta y estado)"""
    query = db.query(Documento)
    
    # Filtrar por carpeta
    if carpeta_id is not None:
        query = query.filter(Documento.carpeta_id == carpeta_id)
    
    # Filtrar solo activos si se solicita
    if solo_activos:
        query = query.filter(Documento.activo == True)
    
    # Si no es admin, solo ver sus documentos
    if current_user.rol != "admin":
        query = query.filter(Documento.usuario_id == current_user.id)
    
    documentos = query.offset(skip).limit(limit).all()
    return documentos

# ==================== OBTENER DOCUMENTO ====================
@router.get("/{documento_id}", response_model=DocumentoResponse)
def obtener_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene un documento por su ID"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    # Verificar permisos
    if current_user.rol != "admin" and documento.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este documento"
        )
    
    return documento

# ==================== ACTUALIZAR DOCUMENTO ====================
@router.put("/{documento_id}", response_model=DocumentoResponse)
def actualizar_documento(
    documento_id: int,
    documento_data: DocumentoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Actualiza un documento (nombre, activo, carpeta) - solo admin"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    update_data = documento_data.model_dump(exclude_unset=True)
    
    # Verificar que la carpeta existe si se está moviendo
    if "carpeta_id" in update_data and update_data["carpeta_id"] is not None:
        carpeta = db.query(Carpeta).filter(Carpeta.id == update_data["carpeta_id"]).first()
        if not carpeta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carpeta no encontrada"
            )
    
    for field, value in update_data.items():
        setattr(documento, field, value)
    
    documento.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(documento)
    
    return documento

# ==================== ACTIVAR/DESACTIVAR DOCUMENTO ====================
@router.patch("/{documento_id}/toggle-activo", response_model=DocumentoResponse)
def toggle_activo_documento(
    documento_id: int,
    toggle_data: DocumentoToggleActivo,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Activa o desactiva un documento - solo admin"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    documento.activo = toggle_data.activo
    documento.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(documento)
    
    return documento

# ==================== ELIMINAR DOCUMENTO ====================
@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Elimina un documento físicamente y sus chunks - solo admin"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    # Eliminar archivo físico
    try:
        if os.path.exists(documento.ruta):
            os.remove(documento.ruta)
    except Exception as e:
        print(f"⚠️ Error al eliminar archivo: {str(e)}")
    
    # Eliminar chunks (cascade automático)
    db.delete(documento)
    db.commit()
    
    return None

# ==================== CONTAR CHUNKS ====================
@router.get("/{documento_id}/chunks-count")
def contar_chunks_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene la cantidad de chunks generados por un documento"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    # Verificar permisos
    if current_user.rol != "admin" and documento.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este documento"
        )
    
    rag_service = RAGService(db)
    count = rag_service.contar_chunks_de_documento(documento_id)
    
    return {"documento_id": documento_id, "chunks_count": count}

# ==================== REPROCESAR DOCUMENTO ====================
@router.post("/{documento_id}/reprocesar", response_model=DocumentoResponse)
async def reprocesar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Reprocesa un documento (rehace chunks y embeddings) - solo admin"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    # Leer el archivo nuevamente
    try:
        with open(documento.ruta, "rb") as f:
            contenido = f.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al leer el archivo: {str(e)}"
        )
    
    # Eliminar chunks viejos
    rag_service = RAGService(db)
    rag_service.eliminar_chunks_de_documento(documento_id)
    
    # Reprocesar
    try:
        rag_service.procesar_documento(documento.id, contenido, documento.tipo_mime)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al reprocesar el documento: {str(e)}"
        )
    
    documento.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(documento)
    
    return documento