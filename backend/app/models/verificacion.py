from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import secrets
from datetime import datetime, timedelta, timezone

class VerificacionToken(Base):
    __tablename__ = "verificaciones_tokens"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    usado = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relación con el usuario
    usuario = relationship("Usuario", backref="verificaciones")
    
    @staticmethod
    def generar_token():
        """Genera un token seguro de 32 bytes en hexadecimal"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def crear_token_expiracion(minutos=1440):  # 24 horas por defecto
        """Crea una fecha de expiración para el token con zona horaria UTC"""
        return datetime.now(timezone.utc) + timedelta(minutes=minutos)
    
    def esta_expirado(self):
        """Verifica si el token ya expiró"""
        return datetime.now(timezone.utc) > self.expira_en
    
    def __repr__(self):
        return f"<VerificacionToken usuario_id={self.usuario_id} expira={self.expira_en}>"