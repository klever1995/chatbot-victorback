from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Carpeta(Base):
    __tablename__ = "carpetas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255), nullable=True)  # Descripción opcional de la carpeta
    
    # Relación jerárquica (subcarpetas)
    padre_id = Column(Integer, ForeignKey("carpetas.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Campos de control
    activa = Column(Boolean, default=True, index=True)  # Para ocultar carpetas sin borrar
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relación con el usuario propietario
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relaciones SQLAlchemy
    usuario = relationship("Usuario", back_populates="carpetas")
    padre = relationship("Carpeta", remote_side=[id], backref="subcarpetas")
    documentos = relationship("Documento", back_populates="carpeta", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Carpeta {self.nombre} (ID: {self.id})>"