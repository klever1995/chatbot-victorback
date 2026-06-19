import os
import requests
import time
from typing import Optional, Dict, Any

WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY")
WAVESPEED_API_BASE = "https://api.wavespeed.ai/api/v3"

class MediaGenerator:
    def __init__(self):
        print("🔧 [MEDIA] Inicializando MediaGenerator...")
        self.headers = {
            "Authorization": f"Bearer {WAVESPEED_API_KEY}",
            "Content-Type": "application/json"
        }
        print("✅ [MEDIA] Headers configurados")

    def _submit_prediction(self, endpoint: str, payload: Dict[str, Any]) -> Optional[str]:
        url = f"{WAVESPEED_API_BASE}/{endpoint}"
        print(f"🚀 [MEDIA] Enviando predicción a {url}")
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            if response.status_code in [200, 201]:
                data = response.json()
                prediction_id = data.get("id") or data.get("data", {}).get("id")
                print(f"✅ [MEDIA] Predicción creada. ID: {prediction_id}")
                return prediction_id
            else:
                print(f"❌ [MEDIA] Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"💥 [MEDIA] Excepción: {e}")
            return None

    def _get_prediction_result(self, prediction_id: str, max_wait: int = 600) -> Optional[Dict[str, Any]]:
        """
        Espera y obtiene el resultado de una predicción.
        Aumentado a 600s para videos que pueden tardar más.
        """
        url = f"{WAVESPEED_API_BASE}/predictions/{prediction_id}/result"
        start_time = time.time()
        intentos = 0
        
        print(f"⏳ [MEDIA] Esperando resultado de predicción {prediction_id} (máx {max_wait}s)...")
        
        while time.time() - start_time < max_wait:
            intentos += 1
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                print(f"📡 [MEDIA] Consulta {intentos} - Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    inner_data = data.get("data", {})
                    status = inner_data.get("status", "unknown")
                    print(f"📊 [MEDIA] Estado de la tarea: {status}")
                    
                    # 🔥 Mostrar más detalles si la tarea falla
                    if status == "failed":
                        error_msg = inner_data.get("error", "Error desconocido")
                        print(f"❌ [MEDIA] Tarea fallida: {error_msg}")
                        print(f"📄 [MEDIA] Respuesta completa: {inner_data}")
                        return None
                        
                    elif status == "completed":
                        print(f"✅ [MEDIA] Tarea completada exitosamente")
                        return inner_data
                        
                    elif status in ["processing", "queued"]:
                        elapsed = int(time.time() - start_time)
                        print(f"⏳ [MEDIA] Procesando... ({elapsed}s transcurridos, esperando 5s)")
                        time.sleep(5)
                        continue
                        
                    else:
                        print(f"⚠️ [MEDIA] Estado desconocido: {status}")
                        print(f"📄 [MEDIA] Respuesta completa: {inner_data}")
                        return None
                        
                elif response.status_code == 404:
                    print(f"⚠️ [MEDIA] Predicción {prediction_id} no encontrada (404)")
                    return None
                else:
                    print(f"⚠️ [MEDIA] Error HTTP {response.status_code}")
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"⏰ [MEDIA] Timeout en consulta {intentos}")
                continue
            except Exception as e:
                print(f"💥 [MEDIA] Excepción en consulta {intentos}: {type(e).__name__}: {str(e)}")
                return None
        
        print(f"⏰ [MEDIA] Tiempo de espera agotado ({max_wait}s) después de {intentos} intentos")
        return None

    def _aspect_ratio_to_size(self, aspect_ratio: str) -> str:
        ratios = {
            "1:1": "1024x1024",
            "4:5": "1024x1280",
            "16:9": "1920x1080",
            "9:16": "1080x1920"
        }
        return ratios.get(aspect_ratio, "1024x1024")

    def generar_imagen(
        self,
        prompt_base: str,
        recomendaciones_extra: Optional[str] = None,
        tono: str = "profesional",
        estilo_visual: str = "minimalista",
        colores_marca: Optional[str] = None,
        objetivo: str = "branding",
        aspect_ratio: str = "1:1",
        logo_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """Genera imagen: sin logo usa flux-2-pro; con logo usa nano-banana-pro/edit"""
        
        size = self._aspect_ratio_to_size(aspect_ratio)
        prompt_completo = prompt_base
        if recomendaciones_extra and recomendaciones_extra.strip():
            prompt_completo = f"{prompt_base}\n\nRecomendaciones adicionales del usuario: {recomendaciones_extra}"
        
        if not logo_base64:
            print(f"🎨 [MEDIA] Generando imagen con flux-2-pro (sin logo)")
            print(f"   - Tamaño: {size}")
            endpoint = "wavespeed-ai/flux-2-pro/text-to-image"
            payload = {
                "prompt": prompt_completo,
                "size": size
            }
            prediction_id = self._submit_prediction(endpoint, payload)
            if not prediction_id:
                return {"success": False, "error": "Error al crear predicción"}
            result = self._get_prediction_result(prediction_id)
            if not result:
                return {"success": False, "error": "Error al obtener resultado"}
            outputs = result.get("outputs", [])
            if outputs and isinstance(outputs, list) and len(outputs) > 0:
                first = outputs[0]
                image_url = first.get("url") if isinstance(first, dict) else first
            else:
                image_url = result.get("url")
            if image_url:
                return {"success": True, "url": image_url, "prompt_optimizado": prompt_completo}
            else:
                return {"success": False, "error": "No se encontró URL"}
        
        print(f"🎨 [MEDIA] Generando imagen con logo usando nano-banana-pro/edit")
        print(f"   - Aspect ratio: {aspect_ratio}")
        prompt_con_logo = prompt_completo + "\n\nIncluye el logo de la marca (imagen proporcionada) en una posición que complemente la composición sin tapar elementos clave. Si es posible, colócalo en la esquina superior izquierda o derecha, manteniendo su forma y colores originales."
        endpoint = "google/nano-banana-pro/edit"
        payload = {
            "prompt": prompt_con_logo,
            "images": [logo_base64],
            "aspect_ratio": aspect_ratio,
            "num_outputs": 1,
            "guidance_scale": 7.5,
            "num_inference_steps": 30
        }
        prediction_id = self._submit_prediction(endpoint, payload)
        if not prediction_id:
            return {"success": False, "error": "Error al crear predicción con logo"}
        result = self._get_prediction_result(prediction_id)
        if not result:
            return {"success": False, "error": "Error al obtener resultado con logo"}
        outputs = result.get("outputs", [])
        if outputs and isinstance(outputs, list) and len(outputs) > 0:
            first = outputs[0]
            image_url = first.get("url") if isinstance(first, dict) else first
        else:
            image_url = result.get("url")
        if image_url:
            return {"success": True, "url": image_url, "prompt_optimizado": prompt_con_logo}
        else:
            return {"success": False, "error": "No se encontró URL con logo"}

    # ==============================
    # GENERACIÓN DE VIDEO CON VIDU Q3
    # ==============================
    def generar_video(
        self,
        prompt_base: str,
        duracion: int = 8,
        imagen_referencia: Optional[str] = None,
        modelo: str = "vidu/q3",
        aspect_ratio: str = "16:9",
        tono: str = "profesional",
        objetivo: str = "branding"
    ) -> Dict[str, Any]:
        """
        Genera un video publicitario usando Vidu Q3 (texto o imagen).
        """
        print(f"🎬 [MEDIA] Generando video con {modelo}")
        print(f"   - Duración: {duracion}s")
        print(f"   - Aspect ratio: {aspect_ratio}")
        print(f"   - Tono: {tono}")
        print(f"   - Objetivo: {objetivo}")
        
        # 🔥 System prompt para video publicitario
        system_prompt = f"""Eres un creador de videos publicitarios profesionales para redes sociales. 
    Tu especialidad es transformar información de productos/servicios en videos atractivos de hasta 16 segundos.

    INSTRUCCIONES:
    1. Genera un video que muestre VISUALMENTE los beneficios, horarios, precios y promociones del producto/servicio.
    2. Usa imágenes claras y profesionales que representen el negocio (ej. personas entrenando, instalaciones, productos).
    3. El video debe tener un flujo narrativo: PROBLEMA → SOLUCIÓN → BENEFICIO → LLAMADO A LA ACCIÓN.
    4. Si la información incluye horarios o precios, intégralos de forma visual (ej. superponiendo texto o mostrando carteles).
    5. El tono debe ser {tono} y el objetivo {objetivo}.
    6. Genera el video con audio sincronizado (música o narración) para darle un toque profesional.
    7. NO generes escenas genéricas sin contexto de la marca.

    Usa esta información del producto/servicio para crear el video:
    {prompt_base}
    """
        
        # Construir prompt completo con system prompt
        prompt_completo = system_prompt.format(
            prompt_base=prompt_base,
            tono=tono,
            objetivo=objetivo
        )
        
        print(f"📝 [MEDIA] Prompt de video (primeros 200 chars): {prompt_completo[:200]}...")
        
        # 🔥 Ajustar duración a los límites de Vidu Q3 (1-16 segundos)
        if duracion < 1:
            duracion = 1
        elif duracion > 16:
            duracion = 16
        
        # 🔥 Vidu Q3 acepta múltiples aspect ratios
        # Validar que aspect_ratio sea válido para Vidu
        valid_aspect_ratios = ["16:9", "9:16", "4:3", "1:1"]
        if aspect_ratio not in valid_aspect_ratios:
            aspect_ratio = "16:9"
            print(f"⚠️ [MEDIA] Aspect ratio no válido, usando 16:9")
        
        if imagen_referencia:
            print(f"   - Imagen referencia: Sí (image-to-video)")
            endpoint = "vidu/q3/image-to-video"
            payload = {
                "image": imagen_referencia,
                "prompt": prompt_completo,
                "duration": duracion,
                "aspect_ratio": aspect_ratio,
                "resolution": "720p",          # 🔥 720p o 1080p
                "generate_audio": True,        # 🔥 Audio sincronizado
                "style": "general"             # 🔥 general, anime, cinematic
            }
        else:
            print(f"   - Imagen referencia: No (text-to-video)")
            endpoint = "vidu/q3/text-to-video"
            payload = {
                "prompt": prompt_completo,
                "duration": duracion,
                "aspect_ratio": aspect_ratio,
                "resolution": "720p",          # 🔥 720p o 1080p
                "generate_audio": True,        # 🔥 Audio sincronizado
                "style": "general"             # 🔥 general, anime, cinematic
            }
        
        prediction_id = self._submit_prediction(endpoint, payload)
        if not prediction_id:
            return {"success": False, "error": "Error al crear predicción de video"}
        
        result = self._get_prediction_result(prediction_id, max_wait=300)
        if not result:
            return {"success": False, "error": "Error al obtener resultado del video"}
        
        video_url = None
        outputs = result.get("outputs", [])
        if outputs and isinstance(outputs, list) and len(outputs) > 0:
            first = outputs[0]
            if isinstance(first, dict):
                video_url = first.get("url") or first.get("video_url")
            elif isinstance(first, str):
                video_url = first
        if not video_url:
            video_url = result.get("url")
        
        if video_url:
            print(f"✅ [MEDIA] Video generado exitosamente: {video_url}")
            return {
                "success": True,
                "url": video_url,
                "prompt_utilizado": prompt_completo,
                "modelo_usado": modelo,
                "duracion": duracion
            }
        else:
            print(f"❌ [MEDIA] No se encontró URL de video en la respuesta: {result}")
            return {"success": False, "error": "No se encontró URL de video"}