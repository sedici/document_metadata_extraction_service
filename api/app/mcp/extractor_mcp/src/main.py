"""
MCP Server for the Extractor Service.

Exposes the extractor's endpoints as MCP tools:
- extract_text: Extracts raw text from a document file.
- extract_text_with_tags: Extracts text preserving structural tags (headings, sections).
- health_check: Returns the liveness status of the extractor service.
- test_integration: Verifies the extractor service is reachable and authenticated.
"""

import os
from mcp.server.fastmcp import FastMCP
import httpx
from dotenv import load_dotenv

load_dotenv()

EXTRACTOR_URL = os.getenv("EXTRACTOR_URL", "http://extractor_service:8001")
EXTRACTOR_TOKEN = os.getenv("EXTRACTOR_TOKEN", "")
MCP_PORT = int(os.getenv("PORT_MCP_EXTRACTOR", 8005))

mcp = FastMCP("extractor-mcp", host="0.0.0.0", port=MCP_PORT)


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {EXTRACTOR_TOKEN}"}


@mcp.tool()
def health_check() -> dict:
    """
    Check the liveness of the extractor service.

    Returns:
        dict: A JSON response with the service status message.
    """
    response = httpx.get(f"{EXTRACTOR_URL}/health", headers=_auth_headers(), timeout=10)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def test_integration() -> dict:
    """
    Verify that the extractor service is up and accepting authenticated requests.

    Returns:
        dict: A JSON response confirming the integration check passed.
    """
    response = httpx.get(
        f"{EXTRACTOR_URL}/test-integration",
        headers=_auth_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def extract_text(
    file_path: str,
    normalization: bool = True,
    ocr: bool = True,
    max_words: int = None,
    multicolumn: bool = False,
    strip_footers: bool = False,
) -> dict:
    """
    Extract plain text from a document file (PDF, DOCX, ODS, etc.).

    Args:
        file_path (str): Absolute path to the input document.
        normalization (bool): Apply text normalization (whitespace cleanup, etc.). Defaults to True.
        ocr (bool): Use OCR to extract text from scanned/image-based pages. Defaults to True.
        max_words (int): Stop extraction after this many words. None means no limit.
        multicolumn (bool): Reorder text column-by-column for multi-column layouts. Defaults to False.
        strip_footers (bool): Remove text in the bottom 6% of each page. Defaults to False.

    Returns:
        dict: API response containing the extracted text under data.text
              and a flag data.is_multicolumn, or an error description.
    """
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    files = {"file": (filename, file_bytes)}
    data = {
        "normalization": str(normalization).lower(),
        "ocr": str(ocr).lower(),
        "multicolumn": str(multicolumn).lower(),
        "strip_footers": str(strip_footers).lower(),
    }
    if max_words is not None:
        data["max_words"] = str(max_words)

    response = httpx.post(
        f"{EXTRACTOR_URL}/extract",
        headers=_auth_headers(),
        files=files,
        data=data,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def extract_text_with_tags(
    file_path: str,
    normalization: bool = True,
    ocr: bool = True,
    max_words: int = None,
) -> dict:
    """
    Extract text from a document preserving structural tags (e.g. section headings).
    The tagged output is used by the orchestrator to improve metadata field detection.

    Args:
        file_path (str): Absolute path to the input document.
        normalization (bool): Apply text normalization. Defaults to True.
        ocr (bool): Use OCR for scanned pages. Defaults to True.
        max_words (int): Stop extraction after this many words. None means no limit.

    Returns:
        dict: API response with tagged text under data.text, or an error description.
    """
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    files = {"file": (filename, file_bytes)}
    data = {
        "normalization": str(normalization).lower(),
        "ocr": str(ocr).lower(),
    }
    if max_words is not None:
        data["max_words"] = str(max_words)

    response = httpx.post(
        f"{EXTRACTOR_URL}/extract-with-tags",
        headers=_auth_headers(),
        files=files,
        data=data,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
