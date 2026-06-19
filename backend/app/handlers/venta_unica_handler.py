import datetime
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.documento import Documento
from app.models.ventas import Venta, EstadoVenta
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones
from app.socket_manager import emitir_nueva_venta

async def procesar_mensaje_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    texto_mensaje: str,
    imagen_info: dict,
    audio_url: str,
    campania_activa: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa un mensaje normal de venta única (respuesta RAG)
    """
    # Si es un comprobante, no procesamos nada aquí (ya se maneja en procesar_comprobante_venta_unica)
    if imagen_info:
        return
    
    rag = RAGService(
        db=db, 
        empresa_id=empresa.id, 
        cliente_id=cliente.id,
        campania_id=campania_activa
    )
    memoria = MemoriaService(db, cliente.id)
    
    print(f"🔍 Buscando documentos para: '{texto_mensaje}' con campaña '{campania_activa}'")
    resumen_cliente = memoria.obtener_resumen()
    documentos_relevantes = rag.buscar_similares(texto_mensaje, top_k=3)
    
    print(f"📚 Documentos encontrados: {len(documentos_relevantes)}")
    for i, doc in enumerate(documentos_relevantes):
        print(f"  {i+1}. Documento: {doc.get('documento', 'N/A')} - Similitud: {doc.get('similitud', 0):.4f}")
        print(f"     Texto: {doc.get('texto', '')[:100]}...")
    
    contexto = "\n\n".join([doc["texto"] for doc in documentos_relevantes])
    
    respuesta_texto = rag.generar_respuesta_llm(
        consulta=texto_mensaje,
        contexto=contexto,
        resumen_cliente=resumen_cliente
    )
    
    if audio_url:
        respuesta_texto = f"🎤 He recibido tu audio. {respuesta_texto}"
    
    mensaje_bot = Conversacion(
        cliente_id=cliente.id,
        mensaje=respuesta_texto,
        emisor=TipoEmisor.BOT
    )
    db.add(mensaje_bot)
    db.commit()
    
    await enviar_mensaje_whatsapp(
        telefono_destino=cliente.telefono,
        mensaje=respuesta_texto,
        token=whatsapp_token,
        phone_number_id=phone_number_id
    )
    
    memoria.actualizar_resumen(texto_mensaje, respuesta_texto)
    
    return respuesta_texto

async def procesar_comprobante_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    url_comprobante: str,
    imagen_info: dict,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa un comprobante de pago para venta única (crea venta PENDIENTE)
    """
    campania_activa = cliente.datos_estructurados.get("campania_activa") if cliente.datos_estructurados else None
    if not campania_activa:
        print("⚠️ No hay campaña activa para el cliente, no se puede registrar venta")
        return False
    
    documento = db.query(Documento).filter(
        Documento.empresa_id == empresa.id,
        Documento.campania_id == campania_activa
    ).first()
    
    if not documento:
        print(f"⚠️ No se encontró documento para campaña {campania_activa}")
        return False
    
    cantidad = 1
    precio_unitario = documento.precio if documento.precio else 0
    monto_total = cantidad * precio_unitario
    
    # 🔥 CREAR VENTA CON ESTADO PENDIENTE
    nueva_venta = Venta(
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        campania_id=campania_activa,
        producto_nombre=documento.nombre.replace('.pdf', ''),
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        monto_total=monto_total,
        estado=EstadoVenta.PENDIENTE,
        comprobante_url=url_comprobante,
        notas=f"Comprobante enviado el {datetime.datetime.now()}"
    )
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)
    
    # 🔥 EMITIR WEBSOCKET PARA VENTA PENDIENTE
    venta_dict = {
        "id": nueva_venta.id,
        "empresa_id": nueva_venta.empresa_id,
        "cliente_id": nueva_venta.cliente_id,
        "cliente_nombre": cliente.nombre or "",
        "cliente_telefono": cliente.telefono,
        "campania_id": nueva_venta.campania_id,
        "producto_nombre": nueva_venta.producto_nombre,
        "cantidad": nueva_venta.cantidad,
        "precio_unitario": nueva_venta.precio_unitario,
        "monto_total": nueva_venta.monto_total,
        "estado": nueva_venta.estado,
        "comprobante_url": nueva_venta.comprobante_url,
        "notas": nueva_venta.notas,
        "fecha_venta": nueva_venta.fecha_venta.isoformat() if nueva_venta.fecha_venta else None,
        "fecha_actualizacion": nueva_venta.fecha_actualizacion.isoformat() if nueva_venta.fecha_actualizacion else None
    }
    await emitir_nueva_venta(venta_dict, empresa.id)
    print(f"📡 Evento WebSocket emitido para venta PENDIENTE ID: {nueva_venta.id}")
    
    # 🔥 GUARDAR ID DE VENTA EN DATOS_ESTRUCTURADOS
    datos_cliente = cliente.datos_estructurados or {}
    datos_cliente["ultimo_comprobante"] = {
        "url": url_comprobante,
        "fecha": str(datetime.datetime.now()),
        "estado_pago": "pendiente",
        "tipo": imagen_info["mime_type"],
        "venta_id": nueva_venta.id
    }
    cliente.datos_estructurados = datos_cliente
    db.commit()
    
    # 🔥 NOTIFICAR AL DUEÑO CON BOTONES
    if empresa.telefono_dueño:
        texto_cabecera = (
            f"🔔 *NUEVO COMPROBANTE - VENTA PENDIENTE*\n\n"
            f"*Venta ID:* {nueva_venta.id}\n"
            f"*Cliente:* {cliente.nombre or 'Desconocido'}\n"
            f"*Teléfono:* {cliente.telefono}\n"
            f"*Producto:* {documento.nombre.replace('.pdf', '')}\n"
            f"*Monto:* ${monto_total:.2f}\n"
            f"*Comprobante:* {url_comprobante}"
        )
        await enviar_mensaje_con_botones(
            telefono_destino=empresa.telefono_dueño,
            texto_cabecera=texto_cabecera,
            cliente_id=cliente.id,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
    
    # 🔥 RESPONDER AL CLIENTE
    mensaje_cliente = f"✅ ¡Gracias por enviar tu comprobante! Hemos registrado tu venta por ${monto_total:.2f}. El dueño lo revisará y te confirmará en breve."
    await enviar_mensaje_whatsapp(
        telefono_destino=cliente.telefono,
        mensaje=mensaje_cliente,
        token=whatsapp_token,
        phone_number_id=phone_number_id
    )
    
    return True

async def aprobar_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente_pendiente: Cliente,
    accion: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa la aprobación o rechazo del dueño para venta única
    """
    datos = cliente_pendiente.datos_estructurados
    campania_cliente = datos.get("campania_activa")
    venta_id = datos.get("ultimo_comprobante", {}).get("venta_id")
    
    # 🔥 BUSCAR LA VENTA PENDIENTE
    venta = None
    if venta_id:
        venta = db.query(Venta).filter(Venta.id == venta_id, Venta.estado == EstadoVenta.PENDIENTE).first()
    
    if not venta:
        print(f"⚠️ No se encontró venta pendiente para cliente {cliente_pendiente.id}")
        return False
    
    if accion == "APROBAR":
        # 🔥 ACTUALIZAR VENTA A CONFIRMADA
        venta.estado = EstadoVenta.CONFIRMADA
        venta.notas = f"Venta aprobada el {datetime.datetime.now()}"
        db.commit()
        db.refresh(venta)
        
        # Actualizar datos del cliente
        datos["ultimo_comprobante"]["estado_pago"] = "confirmado"
        datos["ultimo_comprobante"]["fecha_confirmacion"] = str(datetime.datetime.now())
        cliente_pendiente.datos_estructurados = datos
        db.commit()
        
        # 🔥 EMITIR WEBSOCKET PARA VENTA CONFIRMADA
        venta_dict = {
            "id": venta.id,
            "empresa_id": venta.empresa_id,
            "cliente_id": venta.cliente_id,
            "cliente_nombre": cliente_pendiente.nombre or "",
            "cliente_telefono": cliente_pendiente.telefono,
            "campania_id": venta.campania_id,
            "producto_nombre": venta.producto_nombre,
            "cantidad": venta.cantidad,
            "precio_unitario": venta.precio_unitario,
            "monto_total": venta.monto_total,
            "estado": venta.estado,
            "comprobante_url": venta.comprobante_url,
            "notas": venta.notas,
            "fecha_venta": venta.fecha_venta.isoformat() if venta.fecha_venta else None,
            "fecha_actualizacion": venta.fecha_actualizacion.isoformat() if venta.fecha_actualizacion else None
        }
        await emitir_nueva_venta(venta_dict, empresa.id)
        print(f"📡 Evento WebSocket emitido para venta CONFIRMADA ID: {venta.id}")
        
        # Enviar mensaje de confirmación al cliente
        mensaje_confirmacion = "✅ ¡Buenas noticias! Tu pago ha sido verificado y ya tienes acceso al curso. 😊"
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_confirmacion,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
        
        # Buscar y enviar mensaje de entrega
        print(f"📦 Buscando mensaje de entrega para campaña: {campania_cliente}")
        documento = db.query(Documento).filter(
            Documento.empresa_id == empresa.id,
            Documento.campania_id == campania_cliente
        ).first()
        
        if documento and documento.mensaje_entrega:
            mensaje_material = documento.mensaje_entrega
            print(f"📦 Mensaje de entrega obtenido desde BD")
        else:
            print(f"⚠️ No se encontró mensaje de entrega, usando legacy")
            rag_temp = RAGService(db, empresa.id, cliente_pendiente.id, campania_cliente)
            mensaje_material = rag_temp.obtener_mensaje_entrega_legacy(campania_cliente)
        
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_material,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
        
    else:  # RECHAZAR
        # 🔥 ACTUALIZAR VENTA A RECHAZADA
        venta.estado = EstadoVenta.RECHAZADA
        venta.notas = f"Venta rechazada el {datetime.datetime.now()}"
        db.commit()
        db.refresh(venta)
        
        # Actualizar datos del cliente
        datos["ultimo_comprobante"]["estado_pago"] = "rechazado"
        datos["ultimo_comprobante"]["fecha_rechazo"] = str(datetime.datetime.now())
        cliente_pendiente.datos_estructurados = datos
        db.commit()
        
        # 🔥 EMITIR WEBSOCKET PARA VENTA RECHAZADA
        venta_dict = {
            "id": venta.id,
            "empresa_id": venta.empresa_id,
            "cliente_id": venta.cliente_id,
            "cliente_nombre": cliente_pendiente.nombre or "",
            "cliente_telefono": cliente_pendiente.telefono,
            "campania_id": venta.campania_id,
            "producto_nombre": venta.producto_nombre,
            "cantidad": venta.cantidad,
            "precio_unitario": venta.precio_unitario,
            "monto_total": venta.monto_total,
            "estado": venta.estado,
            "comprobante_url": venta.comprobante_url,
            "notas": venta.notas,
            "fecha_venta": venta.fecha_venta.isoformat() if venta.fecha_venta else None,
            "fecha_actualizacion": venta.fecha_actualizacion.isoformat() if venta.fecha_actualizacion else None
        }
        await emitir_nueva_venta(venta_dict, empresa.id)
        print(f"📡 Evento WebSocket emitido para venta RECHAZADA ID: {venta.id}")
        
        # Enviar mensaje de rechazo al cliente
        mensaje_rechazo = "❌ Hubo un problema con tu comprobante. Por favor, contacta a un asesor para más detalles."
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_rechazo,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
    
    return True