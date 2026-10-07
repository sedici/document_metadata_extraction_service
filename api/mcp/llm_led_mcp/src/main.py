"""
MCP Server for the LLM Service (LED model).

Exposes the llm_service_led endpoints as MCP tools:
- consume_llm: Send text to the LED model and retrieve extracted metadata.
- health_check: Returns the liveness status of the LLM service.
- test_integration: Verifies the LLM service is reachable and authenticated.
"""

import os
from mcp.server.mcpserver import MCPServer
import httpx
from dotenv import load_dotenv

load_dotenv()

LLM_LED_URL = os.getenv("LLM_LED_URL", "http://llm_service_led:8002")
LLM_LED_TOKEN = os.getenv("LLM_LED_TOKEN", "")
MCP_PORT = int(os.getenv("PORT_MCP_LLM_LED", 8006))

mcp = MCPServer("llm-led-mcp")


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {LLM_LED_TOKEN}",
        "Content-Type": "application/json",
    }


@mcp.tool()
def health_check() -> dict:
    """
    Check the liveness of the LLM LED service.

    Returns:
        dict: A JSON response with the service status message.
    """
    headers = {"Authorization": f"Bearer {LLM_LED_TOKEN}"}
    response = httpx.get(f"{LLM_LED_URL}/health", headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def test_integration() -> dict:
    """
    Verify that the LLM LED service is up and accepting authenticated requests.

    Returns:
        dict: A JSON response confirming the integration check passed.
    """
    headers = {"Authorization": f"Bearer {LLM_LED_TOKEN}"}
    response = httpx.get(
        f"{LLM_LED_URL}/test-integration",
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def consume_llm(text: str) -> dict:
    """
    Send text to the LED-based LLM model for structured metadata extraction.

    The model processes the input text and returns a JSON object containing
    document metadata fields (title, creator, date, abstract, etc.) relevant
    for the SEDICI repository.

    Args:
        text (str): The document text (or text with structural tags) to be
                    processed by the model. Should not exceed the model's
                    configured MAX_TOKENS_INPUT limit.

    Returns:
        dict: API response containing extracted metadata under data,
              or an error description if the extraction failed.
    """
    response = httpx.post(
        f"{LLM_LED_URL}/consume-llm",
        headers=_auth_headers(),
        json={"text": text},
        timeout=None,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
