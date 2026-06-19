from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Obtener la URL de la base de datos desde variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://knowledge_user:tu_contraseña@localhost:5435/knowledge_bot_db")

# Crear el motor de SQLAlchemy
engine = create_engine(DATABASE_URL)

# --- NUEVO: Habilitar la extensión vector en PostgreSQL ---
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
# ---------------------------------------------------------

# Crear una fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos declarativos
Base = declarative_base()

# Función para obtener una sesión de base de datos (dependencia para FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()