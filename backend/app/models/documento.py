from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)  # Nombre original del archivo
    nombre_almacenado = Column(String(255), nullable=False, unique=True)  # Nombre único en el servidor
    ruta = Column(String(500), nullable=False)  # Ruta física donde se guardó
    tamano_bytes = Column(BigInteger, nullable=True)  # Tamaño en bytes
    tipo_mime = Column(String(100), nullable=True)  # application/pdf, text/plain, etc.
    extension = Column(String(20), nullable=True)  # .pdf, .docx, .txt, etc.
    
    # Campos específicos para RAG
    activo = Column(Boolean, default=True, index=True)  # Para activar/desactivar documento
    fecha_subida = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    ultimo_acceso = Column(DateTime(timezone=True), nullable=True)  # Última vez que se usó en consultas
    
    # Relaciones
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    carpeta_id = Column(Integer, ForeignKey("carpetas.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Relaciones SQLAlchemy
    usuario = relationship("Usuario", back_populates="documentos")
    carpeta = relationship("Carpeta", back_populates="documentos")
    chunks = relationship("Chunk", back_populates="documento", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Documento {self.nombre} - Activo: {self.activo}>"