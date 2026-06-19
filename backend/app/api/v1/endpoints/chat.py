from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import tempfile
from datetime import datetime

from app.db.base import get_db
from app.models.usuarios import Usuario
from app.models.documento import Documento
from app.api.v1.endpoints.auth import get_current_active_user
from app.services.rag import RAGService
from app.services.voice import VoiceService
from app.schemas.chat import ChatRequest, ChatResponse, AudioChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])

# ==================== CONSULTAR (TEXTO) ====================
@router.post("/consultar", response_model=ChatResponse)
async def consultar(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Consulta al bot usando RAG con documentos activos.
    Si no se especifican documento_ids, usa todos los documentos activos.
    """
    try:
        # Obtener documentos activos si no se especifican
        documento_ids = request.documento_ids
        if documento_ids is None:
            query = db.query(Documento.id).filter(Documento.activo == True)
            if current_user.rol != "admin":
                query = query.filter(Documento.usuario_id == current_user.id)
            documento_ids = [doc[0] for doc in query.all()]
            
            if not documento_ids:
                return ChatResponse(
                    respuesta="No hay documentos activos. Sube documentos primero.",
                    fuentes=[],
                    chunks=[]
                )
        
        rag = RAGService(db)
        resultado = rag.generar_respuesta(
            consulta=request.pregunta,
            documento_ids=documento_ids,
            top_k=request.top_k or 3
        )
        
        return ChatResponse(
            respuesta=resultado["respuesta"],
            fuentes=resultado["fuentes"],
            chunks=resultado["chunks"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar la consulta: {str(e)}"
        )

# ==================== CONSULTAR (AUDIO) ====================
@router.post("/consultar-audio", response_model=ChatResponse)
async def consultar_audio(
    archivo: UploadFile = File(...),
    documento_ids: Optional[str] = Form(None),
    top_k: Optional[int] = Form(3),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """
    Consulta al bot usando un archivo de audio (se transcribe con Groq Whisper).
    """
    try:
        # ✅ FIX: Lista ampliada de tipos permitidos incluyendo M4A y MP4 de Android
        tipos_permitidos = [
            "audio/mpeg",
            "audio/mp3",
            "audio/ogg",
            "audio/wav",
            "audio/webm",
            "audio/mp4",       # ✅ M4A desde expo-audio en Android
            "audio/m4a",       # ✅ M4A alternativo
            "audio/x-m4a",     # ✅ M4A en algunos dispositivos iOS
            "video/mp4",       # ✅ MP4 que graba expo-av (legacy)
            "application/octet-stream",  # ✅ cuando el content_type es genérico
        ]

        content_type = archivo.content_type or "application/octet-stream"
        print(f"🎙️ [AUDIO] Content-Type recibido: {content_type}")

        if content_type not in tipos_permitidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no soportado: '{content_type}'. Permitidos: {', '.join(tipos_permitidos)}"
            )
        
        # Leer el archivo
        contenido = await archivo.read()
        print(f"🎙️ [AUDIO] Tamaño del archivo: {len(contenido)} bytes")

        if len(contenido) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo de audio está vacío."
            )

        # ✅ FIX: Pasar el content_type real como formato_sugerido al VoiceService
        voice = VoiceService()
        try:
            texto_transcrito = voice.transcribir_audio_desde_bytes(
                contenido,
                formato_sugerido=content_type  # ✅ antes no se pasaba esto
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al transcribir el audio: {str(e)}"
            )
        
        if not texto_transcrito or texto_transcrito == "[Error al transcribir el audio]":
            return ChatResponse(
                respuesta="No se pudo transcribir el audio. Por favor, intenta nuevamente.",
                fuentes=[],
                chunks=[]
            )

        print(f"✅ [AUDIO] Transcripción exitosa: '{texto_transcrito[:100]}...'")
        
        # Parsear documento_ids si se enviaron
        doc_ids = None
        if documento_ids:
            try:
                doc_ids = [int(id.strip()) for id in documento_ids.split(',')]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="documento_ids debe ser una lista de números separados por comas (ej: '1,2,3')"
                )
        
        # Generar respuesta con RAG usando el texto transcrito
        rag = RAGService(db)
        resultado = rag.generar_respuesta(
            consulta=texto_transcrito,
            documento_ids=doc_ids,
            top_k=top_k or 3
        )
        
        return ChatResponse(
            respuesta=resultado["respuesta"],
            fuentes=resultado["fuentes"],
            chunks=resultado["chunks"],
            transcripcion=texto_transcrito
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el audio: {str(e)}"
        )