import os
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import magic
from io import BytesIO
from app.models.documento import Documento
from app.models.chunk import Chunk

# Cliente global de OpenAI directo
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

class RAGService:
    def __init__(self, db: Session):
        self.db = db
        
        print("🔍 [RAG DEBUG] Iniciando RAGService con OpenAI directo...")
        
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY no encontrada en variables de entorno")
        
        print(f"🔍 [RAG DEBUG] OPENAI_EMBEDDING_MODEL = {OPENAI_EMBEDDING_MODEL}")
        print(f"🔍 [RAG DEBUG] OPENAI_CHAT_MODEL = {OPENAI_CHAT_MODEL}")
        
        self.tamano_chunk = int(os.getenv("CHUNK_SIZE", 500))
        self.solapamiento = int(os.getenv("CHUNK_OVERLAP", 50))
        
        print("✅ [RAG DEBUG] RAGService inicializado correctamente")
    
    # ==================== EXTRACCIÓN DE TEXTO ====================
    def extraer_texto_pdf(self, archivo_bytes: bytes) -> str:
        print("🔍 [RAG DEBUG] Extrayendo texto del PDF...")
        texto = ""
        pdf = PdfReader(BytesIO(archivo_bytes))
        num_paginas = len(pdf.pages)
        print(f"🔍 [RAG DEBUG] PDF tiene {num_paginas} páginas")
        for i, pagina in enumerate(pdf.pages):
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto += texto_extraido
                print(f"🔍 [RAG DEBUG] Página {i+1}: extraídos {len(texto_extraido)} caracteres")
            else:
                print(f"⚠️ [RAG DEBUG] Página {i+1}: no se pudo extraer texto")
        print(f"🔍 [RAG DEBUG] Texto total extraído: {len(texto)} caracteres")
        return texto
    
    def extraer_texto_docx(self, archivo_bytes: bytes) -> str:
        print("🔍 [RAG DEBUG] Extrayendo texto del DOCX...")
        doc = DocxDocument(BytesIO(archivo_bytes))
        texto = "\n".join([p.text for p in doc.paragraphs])
        print(f"🔍 [RAG DEBUG] Texto extraído: {len(texto)} caracteres")
        return texto
    
    def extraer_texto_txt(self, archivo_bytes: bytes) -> str:
        print("🔍 [RAG DEBUG] Extrayendo texto del TXT...")
        texto = archivo_bytes.decode('utf-8', errors='ignore')
        print(f"🔍 [RAG DEBUG] Texto extraído: {len(texto)} caracteres")
        return texto
    
    def extraer_texto_segun_tipo(self, archivo_bytes: bytes, tipo_mime: str) -> str:
        """Extrae texto según el tipo MIME del archivo"""
        if tipo_mime == "application/pdf":
            return self.extraer_texto_pdf(archivo_bytes)
        elif tipo_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self.extraer_texto_docx(archivo_bytes)
        elif tipo_mime == "text/plain":
            return self.extraer_texto_txt(archivo_bytes)
        else:
            raise ValueError(f"Tipo MIME no soportado: {tipo_mime}")
    
    # ==================== CHUNKING ====================
    def dividir_en_chunks(self, texto: str) -> List[str]:
        print(f"🔍 [RAG DEBUG] Dividiendo texto en chunks (tamaño={self.tamano_chunk}, solapamiento={self.solapamiento})...")
        palabras = texto.split()
        chunks = []
        for i in range(0, len(palabras), self.tamano_chunk - self.solapamiento):
            chunk = " ".join(palabras[i:i + self.tamano_chunk])
            if chunk:
                chunks.append(chunk)
        print(f"🔍 [RAG DEBUG] Generados {len(chunks)} chunks")
        return chunks
    
    # ==================== EMBEDDINGS ====================
    def generar_embedding(self, texto: str) -> List[float]:
        print(f"🔍 [RAG DEBUG] Generando embedding para texto de {len(texto)} caracteres...")
        try:
            respuesta = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=texto
            )
            print("✅ [RAG DEBUG] Embedding generado correctamente")
            return respuesta.data[0].embedding
        except Exception as e:
            print(f"🔴 [RAG DEBUG] Error generando embedding: {type(e).__name__}: {str(e)}")
            raise
    
    # ==================== PROCESAR DOCUMENTO ====================
    def procesar_documento(self, documento_id: int, archivo_bytes: bytes, tipo_mime: str) -> Documento:
        print(f"🔍 [RAG DEBUG] Procesando documento ID={documento_id}, tipo={tipo_mime}")
        
        documento = self.db.query(Documento).filter(Documento.id == documento_id).first()
        if not documento:
            raise ValueError(f"Documento con ID {documento_id} no encontrado")
        
        # Extraer texto según tipo
        texto = self.extraer_texto_segun_tipo(archivo_bytes, tipo_mime)
        if not texto.strip():
            raise ValueError(f"El archivo no contiene texto extraíble")
        
        # Dividir en chunks
        chunks_texto = self.dividir_en_chunks(texto)
        
        # Generar y guardar cada chunk con su embedding
        for i, chunk_texto in enumerate(chunks_texto):
            print(f"🔍 [RAG DEBUG] Procesando chunk {i+1}/{len(chunks_texto)}...")
            embedding = self.generar_embedding(chunk_texto)
            
            # Usar pgvector directamente en SQLAlchemy
            chunk = Chunk(
                documento_id=documento.id,
                indice=i,
                texto=chunk_texto,
                embedding=embedding
            )
            self.db.add(chunk)
        
        # Actualizar documento
        documento.activo = True
        documento.fecha_actualizacion = None  # Se actualiza automáticamente
        self.db.commit()
        print(f"✅ [RAG DEBUG] Documento procesado correctamente. {len(chunks_texto)} chunks guardados en pgvector.")
        return documento
    
    # ==================== BÚSQUEDA SEMÁNTICA ====================
    def buscar_chunks_similares(self, documento_id: int, consulta: str, top_k: int = 5) -> List[Dict[str, Any]]:
        print(f"🔍 [RAG DEBUG] Buscando chunks similares para consulta: '{consulta[:50]}...'")
        embedding_consulta = self.generar_embedding(consulta)
        
        # Usar pgvector para búsqueda por similitud de coseno
        # Convertir embedding a formato PostgreSQL array
        embedding_str = "[" + ",".join([str(x) for x in embedding_consulta]) + "]"
        
        # Consulta SQL con pgvector (operador <=> para distancia coseno)
        query = text("""
            SELECT 
                id, 
                texto, 
                indice,
                documento_id,
                (1 - (embedding <=> :embedding)) as similitud
            FROM chunks
            WHERE documento_id = :documento_id
            ORDER BY embedding <=> :embedding
            LIMIT :top_k
        """)
        
        resultados = self.db.execute(query, {
            "embedding": embedding_str,
            "documento_id": documento_id,
            "top_k": top_k
        }).fetchall()
        
        print(f"🔍 [RAG DEBUG] Encontrados {len(resultados)} chunks similares")
        
        return [
            {
                "chunk_id": r[0],
                "texto": r[1],
                "indice": r[2],
                "documento_id": r[3],
                "similitud": float(r[4])
            }
            for r in resultados
        ]
    
    def buscar_chunks_similares_en_documentos(self, documento_ids: List[int], consulta: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Busca chunks similares en múltiples documentos (para búsqueda global)"""
        if not documento_ids:
            return []
        
        print(f"🔍 [RAG DEBUG] Buscando en {len(documento_ids)} documentos activos")
        embedding_consulta = self.generar_embedding(consulta)
        embedding_str = "[" + ",".join([str(x) for x in embedding_consulta]) + "]"
        
        # Convertir lista de IDs a string para SQL
        ids_str = ",".join([str(id) for id in documento_ids])
        
        query = text(f"""
            SELECT 
                c.id, 
                c.texto, 
                c.indice,
                c.documento_id,
                d.nombre as documento_nombre,
                (1 - (c.embedding <=> :embedding)) as similitud
            FROM chunks c
            JOIN documentos d ON c.documento_id = d.id
            WHERE c.documento_id IN ({ids_str})
                AND d.activo = true
            ORDER BY c.embedding <=> :embedding
            LIMIT :top_k
        """)
        
        resultados = self.db.execute(query, {
            "embedding": embedding_str,
            "top_k": top_k
        }).fetchall()
        
        print(f"🔍 [RAG DEBUG] Encontrados {len(resultados)} chunks en todos los documentos")
        
        return [
            {
                "chunk_id": r[0],
                "texto": r[1],
                "indice": r[2],
                "documento_id": r[3],
                "documento_nombre": r[4],
                "similitud": float(r[5])
            }
            for r in resultados
        ]
    
    # ==================== CONTEXTO PARA GENERACIÓN ====================
    def obtener_contexto_para_generacion(self, documento_ids: List[int], consulta: str, top_k: int = 3) -> str:
        """Obtiene el contexto formateado para pasarlo al LLM"""
        chunks_similares = self.buscar_chunks_similares_en_documentos(documento_ids, consulta, top_k)
        if not chunks_similares:
            return ""
        
        contexto = ""
        for i, chunk in enumerate(chunks_similares):
            if chunk["similitud"] > 0.3:  # Umbral mínimo de relevancia
                contexto += f"[Documento: {chunk['documento_nombre']} - Fragmento {i+1}]:\n{chunk['texto']}\n\n"
        return contexto.strip()
    
    # ==================== ELIMINACIÓN ====================
    def eliminar_chunks_de_documento(self, documento_id: int):
        """Elimina todos los chunks de un documento (para reprocesar o eliminar)"""
        self.db.query(Chunk).filter(Chunk.documento_id == documento_id).delete()
        self.db.commit()
        print(f"🗑️ [RAG DEBUG] Eliminados chunks del documento ID={documento_id}")
    
    def contar_chunks_de_documento(self, documento_id: int) -> int:
        """Cuenta cuántos chunks tiene un documento"""
        return self.db.query(Chunk).filter(Chunk.documento_id == documento_id).count()
    
        # ==================== GENERAR RESPUESTA ====================
    def generar_respuesta(self, consulta: str, documento_ids: Optional[List[int]] = None, top_k: int = 3) -> Dict[str, Any]:
        """
        Genera una respuesta a la consulta del usuario usando el contexto de los documentos activos.
        Actúa como una recepcionista/secretaria virtual, con tono natural y profesional.
        
        Args:
            consulta: Pregunta del usuario
            documento_ids: Lista de IDs de documentos a buscar (si es None, usa todos los activos)
            top_k: Número de chunks a recuperar
        
        Returns:
            Dict con:
                - respuesta: Texto de la respuesta generada
                - fuentes: Lista de documentos usados como fuente
                - chunks: Lista de chunks recuperados con sus similitudes
        """
        print(f"🔍 [RAG DEBUG] Generando respuesta para consulta: '{consulta[:50]}...'")
        
        # Si no se especifican documentos, obtener todos los activos
        if documento_ids is None:
            documentos_activos = self.db.query(Documento).filter(
                Documento.activo == True
            ).all()
            documento_ids = [doc.id for doc in documentos_activos]
            print(f"🔍 [RAG DEBUG] Usando {len(documento_ids)} documentos activos")
        
        if not documento_ids:
            return {
                "respuesta": "Lo siento, aún no tenemos documentos cargados para atender tu consulta. ¿Puedes llamar más tarde?",
                "fuentes": [],
                "chunks": []
            }
        
        # Obtener contexto de los documentos
        contexto = self.obtener_contexto_para_generacion(documento_ids, consulta, top_k)
        
        if not contexto:
            return {
                "respuesta": "No encontré esa información en nuestros documentos, pero puedo ayudarte con otros temas. ¿Qué más necesitas saber?",
                "fuentes": [],
                "chunks": []
            }
        
        # PROMPT PARA RECEPCIONISTA/SECRETARIA VIRTUAL
        prompt = f"""
        Eres una recepcionista o secretaria virtual profesional y amable. Atiendes llamadas telefónicas y respondes preguntas basándote ÚNICAMENTE en los documentos proporcionados.
        
        Contexto de los documentos:
        {contexto}
        
        Pregunta del cliente:
        {consulta}
        
         INSTRUCCIONES ESTRICTAS (IMPERSONAS UNA PERSONA REAL):
        1. Responde con 1 o 2 oraciones como máximo. Sé breve pero completo.
        2. NO uses negritas, asteriscos, guiones, viñetas, emojis, números de lista ni NINGÚN formato.
        3. Habla como una persona: "Claro", "Por supuesto", "Déjame revisar", "Te comento", "Sí, así es".
        4. Si la información no está en el contexto, di: "No tengo esa información en este momento, ¿puedo ayudarte con otra cosa?"
        5. Muestra empatía y profesionalismo: "Entendido", "Perfecto", "Con gusto te ayudo".
        6. Si la pregunta es muy abierta o ambigua, pide aclaración: "¿Podrías ser más específico sobre...?"
        7. Si la información está disponible, dála de forma clara y directa.
        8. NO DES RODEO, ve al grano.
        
        Ejemplos de respuestas correctas:
        - Cliente: "¿Qué servicios ofrecen?"
        - Respuesta: "Ofrecemos consultas generales, vacunación y cirugías. ¿Te interesa alguno en particular?"
        
        - Cliente: "¿Cuánto cuesta la consulta?"
        - Respuesta: "La consulta general cuesta $30, ¿quieres agendar una cita?"
        
        - Cliente: "¿Tienen veterinario de guardia?"
        - Respuesta: "Sí, tenemos guardia las 24 horas para emergencias. ¿Necesitas atención ahora?"
        
        Ahora, responde a la pregunta del cliente siguiendo estas instrucciones al pie de la letra:
        """
        
        try:
            # Generar respuesta con OpenAI con parámetros ajustados
            respuesta = client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "Eres una recepcionista/secretaria virtual profesional, amable y natural. Respondes preguntas brevemente, como en una llamada telefónica."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Más natural y conversacional
                max_tokens=150    # Respuestas muy cortas (como una persona real)
            )
            
            texto_respuesta = respuesta.choices[0].message.content.strip()
            
            # Limpiar caracteres especiales y formato residual
            texto_respuesta = texto_respuesta.replace('**', '').replace('*', '').replace('#', '').replace('- ', '')
            texto_respuesta = texto_respuesta.replace('\n', ' ').replace('  ', ' ')
            texto_respuesta = texto_respuesta.replace('"', '').replace("'", "")
            
            # Extraer fuentes (documentos usados)
            chunks_similares = self.buscar_chunks_similares_en_documentos(documento_ids, consulta, top_k)
            fuentes = list(set([chunk["documento_nombre"] for chunk in chunks_similares if chunk["similitud"] > 0.3]))
            
            return {
                "respuesta": texto_respuesta,
                "fuentes": fuentes,
                "chunks": chunks_similares
            }
            
        except Exception as e:
            print(f"🔴 [RAG DEBUG] Error generando respuesta: {type(e).__name__}: {str(e)}")
            return {
                "respuesta": "Lo siento, hubo un problema técnico. ¿Puedes repetir tu pregunta?",
                "fuentes": [],
                "chunks": []
            }