from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    activa = Column(Boolean, default=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relación con usuarios (una empresa puede tener varios usuarios, aunque al inicio cada usuario = una empresa)
    # Esto te permite en el futuro ofrecer planes multiusuario

    def __repr__(self):
        return f"<Empresa {self.nombre}>"