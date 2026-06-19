from sqlalchemy.orm import Session
from app.models.usuario import Usuario
from app.models.conversacion import Conversacion, Mensaje
from typing import Optional, List, Dict
from datetime import datetime
import json

class MemoriaService:
    def __init__(self, db: Session, usuario_id: int):
        self.db = db
        self.usuario_id = usuario_id
        self.usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    # ==================== CONVERSACIONES ====================
    def crear_conversacion(self, titulo: Optional[str] = None) -> Conversacion:
        """Crea una nueva conversación para el usuario"""
        conversacion = Conversacion(
            usuario_id=self.usuario_id,
            titulo=titulo or f"Conversación {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            activa=True
        )
        self.db.add(conversacion)
        self.db.commit()
        self.db.refresh(conversacion)
        return conversacion
    
    def obtener_conversaciones_activas(self) -> List[Conversacion]:
        """Obtiene todas las conversaciones activas del usuario"""
        return self.db.query(Conversacion).filter(
            Conversacion.usuario_id == self.usuario_id,
            Conversacion.activa == True
        ).order_by(Conversacion.fecha_actualizacion.desc()).all()
    
    def obtener_conversacion(self, conversacion_id: int) -> Optional[Conversacion]:
        """Obtiene una conversación específica si pertenece al usuario"""
        return self.db.query(Conversacion).filter(
            Conversacion.id == conversacion_id,
            Conversacion.usuario_id == self.usuario_id
        ).first()
    
    def cerrar_conversacion(self, conversacion_id: int) -> bool:
        """Desactiva una conversación"""
        conversacion = self.obtener_conversacion(conversacion_id)
        if not conversacion:
            return False
        conversacion.activa = False
        self.db.commit()
        return True
    
    # ==================== MENSAJES ====================
    def agregar_mensaje(self, conversacion_id: int, rol: str, texto: str, fuentes: Optional[Dict] = None) -> Mensaje:
        """Agrega un mensaje a la conversación y actualiza la fecha de último mensaje"""
        mensaje = Mensaje(
            conversacion_id=conversacion_id,
            rol=rol,  # "usuario" o "asistente"
            texto=texto,
            fuentes=json.dumps(fuentes) if fuentes else None
        )
        self.db.add(mensaje)
        
        # Actualizar fecha de último mensaje en la conversación
        conversacion = self.obtener_conversacion(conversacion_id)
        if conversacion:
            conversacion.ultimo_mensaje = datetime.now()
        
        self.db.commit()
        self.db.refresh(mensaje)
        return mensaje
    
    def obtener_historial(self, conversacion_id: int, limite: Optional[int] = None) -> List[Mensaje]:
        """Obtiene el historial de mensajes de una conversación (opcionalmente con límite)"""
        query = self.db.query(Mensaje).filter(
            Mensaje.conversacion_id == conversacion_id
        ).order_by(Mensaje.fecha.asc())
        
        if limite:
            query = query.limit(limite)
        
        return query.all()
    
    def obtener_historial_con_contexto(self, conversacion_id: int, ultimos_n: int = 10) -> List[Dict]:
        """Obtiene el historial formateado para pasarlo al LLM como contexto"""
        mensajes = self.obtener_historial(conversacion_id, limite=ultimos_n)
        return [{"rol": m.rol, "texto": m.texto} for m in mensajes]
    
    # ==================== CONTEXTO Y RESUMEN ====================
    def actualizar_titulo_conversacion(self, conversacion_id: int, nuevo_titulo: str):
        """Actualiza el título de una conversación (ej: generado por LLM)"""
        conversacion = self.obtener_conversacion(conversacion_id)
        if conversacion:
            conversacion.titulo = nuevo_titulo
            self.db.commit()
    
    def obtener_ultimo_mensaje(self, conversacion_id: int) -> Optional[Mensaje]:
        """Obtiene el último mensaje de una conversación"""
        return self.db.query(Mensaje).filter(
            Mensaje.conversacion_id == conversacion_id
        ).order_by(Mensaje.fecha.desc()).first()