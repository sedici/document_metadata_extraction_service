# API — Servicios de extracción de metadatos

## Estructura

```
api/
├── app/                  ← Microservicios HTTP (core del sistema)
│   ├── docker-compose.yml
│   ├── extractor_service/
│   ├── llm_service/
│   ├── orchestrator/
│   └── models/
└── mcp/                  ← Adaptadores MCP (interfaz para agentes de IA)
    ├── orchestrator_mcp/
    ├── extractor_mcp/
    └── llm_led_mcp/
```

## Servicios (`api/app`)

- **extractor_service**: recibe un documento (PDF, DOCX, ODS) y extrae el texto plano o en formato XML etiquetado.
- **llm_service**: recibe texto procesado y un prompt, y ejecuta un modelo de lenguaje para extraer metadatos estructurados.
- **orchestrator**: punto de entrada principal. Coordina el flujo entre `extractor_service` y `llm_service`, detecta el tipo de documento y retorna el JSON de metadatos.

## MCP Servers (`api/mcp`)

Wrappers de protocolo MCP que exponen los servicios HTTP anteriores como *tools* consumibles por agentes de IA (Claude, LangGraph, etc.):

- **orchestrator_mcp**: expone el endpoint de upload del orquestador.
- **extractor_mcp**: expone el endpoint de extracción de texto.
- **llm_led_mcp**: expone el endpoint del modelo de lenguaje.

## Cómo ejecutar

### Con Docker Compose (recomendado)

```bash
# Desde api/app/
docker-compose up
# Solo servicios core (sin MCP):
docker-compose up orchestrator extractor_service llm_service_led
# Solo un servicio:
docker-compose up extractor_service
```

Configurar variables de entorno en `.env` (ver `.env.example`).

### Sin contenedores (Python 3.10+)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```