# ChatPDFcode - Backend del Sistema de Chatbot para PDFs Académicos

## Descripción
Backend API desarrollado con FastAPI para procesar documentos PDF académicos 
y responder consultas usando arquitectura RAG (Retrieval-Augmented Generation).

## Tecnologías
- **FastAPI** - Framework API asincrónico
- **Celery + Redis** - Procesamiento asincrónico
- **Qdrant** - Base de datos vectorial
- **PyMuPDF + Tesseract** - Procesamiento de PDFs
- **OpenAI GPT-4** - Modelo de lenguaje

## Estructura
```
ChatPDFcode/
├── app/
│   ├── api/routes/      # Endpoints
│   ├── core/            # Lógica de negocio
│   ├── llm/             # Integración LLM
│   ├── db/              # Redis + Qdrant
│   ├── workers/         # Tareas Celery
│   └── models/          # Esquemas Pydantic
├── tests/
├── docker-compose.yml
└── requirements.txt
```

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
copy .env.example .env
# Editar .env con tus API keys

# Ejecutar con Docker (recomendado)
docker-compose up --build

# O ejecutar localmente
uvicorn app.main:app --reload
```

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/session/create` | Crear sesión |
| POST | `/api/documents/upload` | Subir PDFs |
| GET | `/api/documents/status/{job_id}` | Estado de procesamiento |
| POST | `/api/chat/message` | Enviar pregunta |
| GET | `/api/chat/history/{session_id}` | Historial de chat |
| DELETE | `/api/session/close/{session_id}` | Cerrar sesión |

## Licencia
MIT
