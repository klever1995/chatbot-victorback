from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from passlib.context import CryptContext
import os
from typing import List

from app.db.base import get_db
from app.models.usuarios import Usuario
from app.models.empresa import Empresa
from app.models.verificacion import VerificacionToken
from app.schemas.usuarios import UsuarioCreate, UsuarioResponse, UsuarioUpdate, UsuarioAdminCreate
from app.api.v1.endpoints.auth import get_current_active_user, get_current_admin_user
from app.services.email import enviar_email_verificacion

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

def get_password_hash(password):
    return pwd_context.hash(password)

# ==================== ENDPOINT PÚBLICO (REGISTRO) ====================
@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    usuario: UsuarioCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Registro de nuevo usuario con verificación por email"""
    
    # Verificar que el email no esté registrado
    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email ya registrado"
        )
    
    # Crear la empresa automáticamente (una empresa por usuario)
    nueva_empresa = Empresa(
        nombre=f"Empresa de {usuario.nombre}",
        activa=True
    )
    db.add(nueva_empresa)
    db.flush()
    
    # Crear nuevo usuario asociado a esa empresa (INACTIVO hasta verificar email)
    nuevo_usuario = Usuario(
        empresa_id=nueva_empresa.id,
        email=usuario.email,
        nombre=usuario.nombre,
        password_hash=get_password_hash(usuario.password),
        rol="usuario",
        activo=False,
        auth_provider="local"
    )
    
    db.add(nuevo_usuario)
    db.flush()
    
    # Generar token de verificación (expira en 24 horas)
    token = VerificacionToken.generar_token()
    expiracion = VerificacionToken.crear_token_expiracion(minutos=1440)
    
    verificacion_token = VerificacionToken(
        usuario_id=nuevo_usuario.id,
        token=token,
        expira_en=expiracion,
        usado=False
    )
    db.add(verificacion_token)
    db.commit()
    
    # Construir enlace de verificación
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    enlace_verificacion = f"{frontend_url}/verificar-email?token={token}"
    
    # Enviar email en segundo plano
    background_tasks.add_task(
        enviar_email_verificacion,
        email_destino=usuario.email,
        nombre=usuario.nombre,
        enlace=enlace_verificacion
    )
    
    db.refresh(nuevo_usuario)
    
    return nuevo_usuario

# ==================== ENDPOINT PÚBLICO (VERIFICACIÓN) ====================
@router.get("/verificar-email")
def verificar_email(
    token: str,
    db: Session = Depends(get_db)
):
    """Verifica el email del usuario mediante el token"""
    
    # Buscar el token
    verificacion = db.query(VerificacionToken).filter(
        VerificacionToken.token == token,
        VerificacionToken.usado == False
    ).first()
    
    if not verificacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o ya usado"
        )
    
    if verificacion.esta_expirado():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expirado. Solicita un nuevo enlace de verificación"
        )
    
    # Activar al usuario
    usuario = db.query(Usuario).filter(Usuario.id == verificacion.usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    usuario.activo = True
    verificacion.usado = True
    
    db.commit()
    
    return {"mensaje": "Email verificado correctamente. Ya puedes iniciar sesión."}

# ==================== ENDPOINTS PROTEGIDOS (USUARIO AUTENTICADO) ====================
# 🔥 IMPORTANTE: Los endpoints /me DEBEN ir ANTES de las rutas con parámetros
@router.get("/me", response_model=UsuarioResponse)
def leer_usuario_actual(
    current_user: Usuario = Depends(get_current_active_user)
):
    """Obtiene el perfil del usuario autenticado"""
    return current_user

@router.put("/me", response_model=UsuarioResponse)
def actualizar_mi_usuario(
    usuario_update: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Actualiza el perfil del usuario autenticado"""
    
    update_data = usuario_update.model_dump(exclude_unset=True)
    
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    
    if "email" in update_data:
        email_existente = db.query(Usuario).filter(
            Usuario.email == update_data["email"],
            Usuario.id != current_user.id
        ).first()
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ya registrado"
            )
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mi_usuario(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Elimina la cuenta del usuario autenticado (borrado físico)"""
    
    # Verificar si tiene documentos asociados
    if current_user.documentos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu cuenta porque tienes documentos asociados. Elimina primero tus documentos."
        )
    
    db.delete(current_user)
    db.commit()
    
    return None

# ==================== ENDPOINTS ADMIN ====================
@router.get("/", response_model=List[UsuarioResponse])
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Lista todos los usuarios (solo para administradores)"""
    usuarios = db.query(Usuario).offset(skip).limit(limit).all()
    return usuarios

@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Obtiene un usuario por su ID (solo para administradores)"""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return usuario

@router.put("/{usuario_id}/rol", response_model=UsuarioResponse)
def cambiar_rol_usuario(
    usuario_id: int,
    nuevo_rol: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Cambia el rol de un usuario (solo para administradores)"""
    if nuevo_rol not in ["usuario", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol inválido. Debe ser 'usuario' o 'admin'"
        )
    
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol"
        )
    
    usuario.rol = nuevo_rol
    usuario.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(usuario)
    
    return usuario

@router.put("/{usuario_id}/activar", response_model=UsuarioResponse)
def activar_desactivar_usuario(
    usuario_id: int,
    activo: bool,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user)
):
    """Activa o desactiva un usuario (solo para administradores)"""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if usuario.id == current_user.id and not activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta"
        )
    
    usuario.activo = activo
    usuario.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(usuario)
    
    return usuario