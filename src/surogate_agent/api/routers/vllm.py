"""
vLLM proxy endpoints.

GET /api/vllm/models?url=<base_url>
    Fetches the model list from a vLLM (or any OpenAI-compatible) endpoint
    server-side, bypassing browser CORS and SSL certificate restrictions.
    Equivalent to: curl -k {url}/v1/models
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import User
from surogate_agent.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/vllm", tags=["vllm"])


@router.get("/models")
async def list_vllm_models(
    url: str = Query(..., description="Base URL of the vLLM endpoint, e.g. http://localhost:8000"),
    _: User = Depends(get_current_user),
) -> list[str]:
    """Proxy GET {url}/v1/models and return a list of model IDs.

    Uses ``verify=False`` (equivalent to ``curl -k``) so self-signed certificates
    are accepted.  Only authenticated users can call this endpoint.
    """
    try:
        import httpx
    except ImportError:
        raise HTTPException(status_code=500, detail="httpx is not installed. Run: pip install httpx")

    base = url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    models_url = f"{base}/models"

    log.debug("proxying vLLM models request: %s", models_url)
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(models_url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout connecting to {models_url}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach endpoint: {exc}")

    models = [m["id"] for m in data.get("data", []) if m.get("id")]
    log.debug("vLLM models at %s: %s", models_url, models)
    return models
