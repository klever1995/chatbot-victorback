import os
import requests
from groq import Groq
from typing import Optional
import magic

class VoiceService:
    """
    Servicio para manejar operaciones de voz usando Groq Whisper
    """
    
    # Mapeo de tipos MIME a extensiones aceptadas por Groq
    MIME_TO_GROQ = {
        'audio/mpeg': 'mp3',
        'audio/mp3': 'mp3',
        'audio/mp4': 'm4a',
        'audio/m4a': 'm4a',
        'audio/ogg': 'ogg',
        'audio/opus': 'opus',
        'audio/wav': 'wav',
        'audio/webm': 'webm',
        'audio/flac': 'flac',
        'audio/x-flac': 'flac',
        'audio/3gpp': '3gp',
        'audio/3gpp2': '3gp',
        'audio/x-m4a': 'm4a',
        'audio/x-wav': 'wav',
        'video/mp4': 'ogg',
        'video/3gpp': 'ogg',
        'video/quicktime': 'ogg',
    }
    
    # Extensiones aceptadas por Groq
    EXTENSIONES_ACEPTADAS = ['flac', 'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'opus', 'wav', 'webm']
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY no encontrada en variables de entorno")
        
        self.client = Groq(api_key=self.api_key)
        self.model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
    
    def _detectar_formato(self, archivo_bytes: bytes, formato_sugerido: Optional[str] = None) -> str:
        """
        Detecta el formato MIME real del archivo usando magic y lo convierte a un formato aceptado por Groq.
        Si no se puede detectar, usa el formato_sugerido o 'ogg' como fallback.
        """
        # PRIORIDAD: Si el frontend envió un formato sugerido, usarlo primero
        if formato_sugerido:
            print(f"🔍 [VOICE DEBUG] Formato sugerido por el frontend: {formato_sugerido}")
            # Extraer la extensión del MIME sugerido (ej: "audio/mp4" -> "mp4")
            if '/' in formato_sugerido:
                ext = formato_sugerido.split('/')[-1]
                if ext in self.EXTENSIONES_ACEPTADAS:
                    print(f"🔍 [VOICE DEBUG] Usando formato sugerido: {ext}")
                    return ext
            elif formato_sugerido in self.EXTENSIONES_ACEPTADAS:
                print(f"🔍 [VOICE DEBUG] Usando formato sugerido: {formato_sugerido}")
                return formato_sugerido
        
        # Si no hay formato sugerido o no es válido, usar magic
        try:
            mime_type = magic.from_buffer(archivo_bytes, mime=True)
            print(f"🔍 [VOICE DEBUG] MIME detectado por magic: {mime_type}")
            
            if mime_type in self.MIME_TO_GROQ:
                formato_groq = self.MIME_TO_GROQ[mime_type]
                print(f"🔍 [VOICE DEBUG] Formato mapeado a: {formato_groq}")
                return formato_groq
            else:
                print(f"⚠️ [VOICE DEBUG] MIME '{mime_type}' no mapeado")
        except Exception as e:
            print(f"⚠️ [VOICE DEBUG] Error detectando MIME: {e}")
        
        # Fallback final: ogg
        print("🔍 [VOICE DEBUG] Fallback final: ogg")
        return 'ogg'
    
    def transcribir_audio(self, url_audio: str, token: Optional[str] = None) -> str:
        """
        Transcribe un audio desde una URL usando Groq Whisper
        
        Args:
            url_audio: URL del archivo de audio
            token: Token de autorización (opcional, para archivos protegidos)
        
        Returns:
            Texto transcrito del audio
        """
        try:
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            response = requests.get(url_audio, headers=headers)
            response.raise_for_status()
            
            contenido = response.content
            formato = self._detectar_formato(contenido)
            
            archivo = (f"audio.{formato}", contenido, f"audio/{formato}")
            
            transcripcion = self.client.audio.transcriptions.create(
                file=archivo,
                model=self.model,
                response_format="text"
            )
            
            return transcripcion
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error descargando audio: {e}")
            raise Exception(f"Error al descargar el audio: {str(e)}")
        except Exception as e:
            print(f"❌ Error en transcripción con Groq: {type(e).__name__}: {str(e)}")
            raise Exception(f"Error al transcribir el audio: {str(e)}")
    
    def transcribir_audio_desde_bytes(self, archivo_bytes: bytes, formato_sugerido: Optional[str] = None) -> str:
        """
        Transcribe un audio desde bytes usando Groq Whisper
        
        Args:
            archivo_bytes: Contenido del archivo de audio en bytes
            formato_sugerido: Tipo MIME o extensión sugerida (ej: "audio/m4a", "m4a")
        
        Returns:
            Texto transcrito del audio
        """
        try:
            formato = self._detectar_formato(archivo_bytes, formato_sugerido)
            print(f"🔍 [VOICE DEBUG] Formato final usado: {formato}")
            
            archivo = (f"audio.{formato}", archivo_bytes, f"audio/{formato}")
            
            transcripcion = self.client.audio.transcriptions.create(
                file=archivo,
                model=self.model,
                response_format="text"
            )
            
            return transcripcion
            
        except Exception as e:
            print(f"❌ Error en transcripción con Groq: {type(e).__name__}: {str(e)}")
            raise Exception(f"Error al transcribir el audio: {str(e)}")