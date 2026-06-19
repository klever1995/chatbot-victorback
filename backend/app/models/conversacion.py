from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Conversacion(Base):
    __tablename__ = "conversaciones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(255), nullable=True)  # Título generado automáticamente (ej: "Consulta sobre ventas")
    activa = Column(Boolean, default=True, index=True)  # Para cerrar conversaciones viejas
    fecha_inicio = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    ultimo_mensaje = Column(DateTime(timezone=True), nullable=True)  # Última interacción

    # Relaciones
    usuario = relationship("Usuario", backref="conversaciones")
    mensajes = relationship("Mensaje", back_populates="conversacion", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversacion {self.id} - Usuario: {self.usuario_id} - Activa: {self.activa}>"


class Mensaje(Base):
    __tablename__ = "mensajes"

    id = Column(Integer, primary_key=True, index=True)
    conversacion_id = Column(Integer, ForeignKey("conversaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    rol = Column(String(20), nullable=False)  # "usuario" o "asistente"
    texto = Column(Text, nullable=False)
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    
    # Opcional: guardar metadatos como fuentes usadas en la respuesta
    fuentes = Column(Text, nullable=True)  # JSON con IDs de documentos/chunks usados

    # Relaciones
    conversacion = relationship("Conversacion", back_populates="mensajes")

    def __repr__(self):
        return f"<Mensaje {self.id} - {self.rol}: {self.texto[:50]}...>"