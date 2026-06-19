from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
from pgvector.sqlalchemy import Vector

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(Integer, ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True)
    indice = Column(Integer, nullable=False)  # Orden del chunk dentro del documento
    texto = Column(Text, nullable=False)  # El fragmento de texto en sí
    embedding = Column(Vector(1536))  # Vector de 1536 dimensiones (para OpenAI text-embedding-3-small)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())

    # Relación con el documento padre
    documento = relationship("Documento", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk documento_id={self.documento_id} índice={self.indice}>"