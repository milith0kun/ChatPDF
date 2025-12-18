# ChatPDF - Sistema de Chatbot Inteligente para PDFs Académicos

<div align="center">

![ChatPDF Logo](ChatUI/public/chatpdf.svg)

**Analiza documentos PDF académicos usando inteligencia artificial**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

## 📋 Descripción

ChatPDF es un sistema de chatbot conversacional que permite:
- 📄 Cargar múltiples documentos PDF académicos
- 🤖 Hacer preguntas en lenguaje natural sobre el contenido
- 🔍 Obtener respuestas precisas con referencias a páginas específicas
- 🛡️ Prevención de alucinaciones (solo responde con información del documento)

## 🏗️ Arquitectura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ChatUI        │────▶│   FastAPI       │────▶│   GPT-4         │
│   (React)       │     │   Backend       │     │   OpenAI        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌─────────┐┌─────────┐┌─────────┐
              │  Redis  ││ Qdrant  ││ Celery  │
              │ Sesiones││Vectores ││ Workers │
              └─────────┘└─────────┘└─────────┘
```

## 🚀 Inicio Rápido

### Requisitos
- Docker & Docker Compose
- API Key de OpenAI

### Instalación

```bash
# 1. Clonar el repositorio
git clone <tu-repo>
cd ChatPdf

# 2. Configurar variables de entorno
cd ChatPDFcode
cp .env.example .env
# Editar .env con tu OPENAI_API_KEY

# 3. Iniciar con Docker
docker-compose up --build

# 4. En otra terminal, iniciar el frontend
cd ../ChatUI
npm install
npm run dev
```

### URLs
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Qdrant**: http://localhost:6333/dashboard

## 📁 Estructura del Proyecto

```
ChatPdf/
├── ChatPDFcode/              # Backend Python
│   ├── app/
│   │   ├── api/routes/       # Endpoints REST
│   │   ├── core/             # Procesamiento PDF, RAG
│   │   ├── llm/              # Integración OpenAI
│   │   ├── db/               # Redis, Qdrant
│   │   └── workers/          # Tareas Celery
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── ChatUI/                   # Frontend React
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── services/api.js
│   └── package.json
│
└── Readme.md
```

## 🔧 Tecnologías

| Componente | Tecnología |
|------------|------------|
| Backend | FastAPI, Python 3.11 |
| Frontend | React 18, Vite |
| Vector DB | Qdrant |
| Cache | Redis |
| Queue | Celery |
| PDF Processing | PyMuPDF, Tesseract OCR |
| Embeddings | sentence-transformers |
| LLM | OpenAI GPT-4 Turbo |

## 📖 API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/session/create` | Crear sesión |
| POST | `/api/documents/upload` | Subir PDFs |
| GET | `/api/documents/status/{job_id}` | Estado de procesamiento |
| POST | `/api/chat/message` | Enviar pregunta |
| GET | `/api/chat/history/{session_id}` | Historial |
| DELETE | `/api/session/close/{session_id}` | Cerrar sesión |

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Añadir nueva funcionalidad'`)
4. Push (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.