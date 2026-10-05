"""
MCP Server for the Orchestrator Service.

Exposes the orchestrator's endpoints as MCP tools:
- upload_document: Sends a document to the orchestrator for metadata extraction.
- test_integration: Checks the health of all downstream services.
- health_check: Returns the liveness status of the orchestrator.
"""

import os
import base64
from mcp.server.mcpserver import MCPServer
import httpx
from dotenv import load_dotenv

load_dotenv()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")
ORCHESTRATOR_TOKEN = os.getenv("ORCHESTRATOR_TOKEN", "")
MCP_PORT = int(os.getenv("PORT_MCP_ORCHESTRATOR", 8004))

mcp = MCPServer("orchestrator-mcp")


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {ORCHESTRATOR_TOKEN}"}


# TODO: ver si esto es necesario
# @mcp.tool()
# def test_integration() -> dict:
#     """
#     Verify that the orchestrator can reach all downstream services
#     (extractor_service and llm_service_led).

#     Returns:
#         dict: A JSON response indicating whether all integration checks passed.
#     """
#     response = httpx.get(
#         f"{ORCHESTRATOR_URL}/test-integration",
#         headers=_auth_headers(),
#         timeout=30,
#     )
#     response.raise_for_status()
#     return response.json()

@mcp.tool()
def upload_document(
    file_path: str,
    normalization: bool = True,
    doc_type: str = "None",
    deepanalyze: bool = False,
    ocr: bool = False,
) -> dict:
    """
    Upload a document to the orchestrator for metadata extraction.

    The orchestrator will:
    1. Extract text via the extractor_service.
    2. Predict the document type and subject.
    3. Run the appropriate LLM strategy to extract structured metadata.

    Args:
        file_path (str): Absolute path to the document file (PDF, DOCX, ODS).
        normalization (bool): Whether to apply text normalization. Defaults to True.
        doc_type (str): Document type hint. One of "Articulo", "Libro", "Tesis",
                        "Objeto de conferencia", "General", or "None" (auto-detect).
                        Defaults to "None".
        deepanalyze (bool): Whether to run the deep-analysis LLM pass. Defaults to False.
        ocr (bool): Whether to apply OCR for scanned pages. Defaults to False.

    Returns:
        dict: Extracted metadata as a JSON object, or an error description.
    """
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    files = {"file": (filename, file_bytes)}
    data = {
        "normalization": str(normalization).lower(),
        "type": doc_type,
        "deepanalyze": str(deepanalyze).lower(),
        "ocr": str(ocr).lower(),
    }

    response = httpx.post(
        f"{ORCHESTRATOR_URL}/upload",
        headers=_auth_headers(),
        files=files,
        data=data,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)
