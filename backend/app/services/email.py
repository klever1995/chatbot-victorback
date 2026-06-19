import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def enviar_email_verificacion(email_destino: str, nombre: str, enlace: str):
    """Envía email de verificación usando SMTP (configura con tus credenciales)"""
    
    # Configuración desde variables de entorno
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        print(f"⚠️ No hay configuración SMTP. Enlace de verificación para {nombre}: {enlace}")
        return
    
    asunto = "Verifica tu cuenta - Chatbot IA"
    html = f"""
    <h2>Hola {nombre},</h2>
    <p>Gracias por registrarte en <strong>Chatbot IA</strong>. Para activar tu cuenta, haz clic en el siguiente enlace:</p>
    <p><a href="{enlace}">{enlace}</a></p>
    <p>Este enlace expira en 24 horas.</p>
    <p>Si no solicitaste este registro, ignora este mensaje.</p>
    <br>
    <p>Saludos,<br>Equipo de Chatbot IA</p>
    """
    
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_destino
    msg["Subject"] = asunto
    msg.attach(MIMEText(html, "html"))
    
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"✅ Email de verificación enviado a {email_destino}")
    except Exception as e:
        print(f"❌ Error enviando email: {str(e)}")