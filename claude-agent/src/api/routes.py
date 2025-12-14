"""FastAPI routes for n8n integration and health checks."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models

class QueryRequest(BaseModel):
    """General query request."""
    prompt: str
    context: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    """General query response."""
    response: str
    success: bool


class HealthAnalysisRequest(BaseModel):
    """Request for health analysis from n8n workflow."""
    devices: list[dict[str, Any]]
    summary: str


class HealthAnalysisResponse(BaseModel):
    """Response for health analysis."""
    analysis: str
    success: bool


class AuditAnalysisRequest(BaseModel):
    """Request for audit analysis from n8n workflow."""
    networks: list[dict[str, Any]]
    wlans: list[dict[str, Any]]
    firewall_rules: list[dict[str, Any]]
    devices: list[dict[str, Any]]
    findings: list[dict[str, Any]]


class AuditAnalysisResponse(BaseModel):
    """Response for audit analysis."""
    recommendations: str
    success: bool


class KnowledgeSearchRequest(BaseModel):
    """Request for knowledge base search."""
    query: str
    n_results: int = 5


class KnowledgeSearchResponse(BaseModel):
    """Response for knowledge base search."""
    results: list[dict[str, Any]]
    success: bool


# Routes

@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check(request: Request) -> dict[str, Any]:
    """Readiness check with component status."""
    agent = getattr(request.app.state, "agent", None)
    kb = getattr(request.app.state, "knowledge_base", None)

    return {
        "status": "ready" if agent else "initializing",
        "components": {
            "agent": "ready" if agent else "not initialized",
            "knowledge_base": kb.get_stats() if kb else {"status": "not initialized"},
        },
    }


@router.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest, req: Request) -> QueryResponse:
    """General query endpoint for the agent.

    Use this endpoint for ad-hoc questions to the UniFi Expert.
    """
    agent = getattr(req.app.state, "agent", None)
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        response = await agent.query(request.prompt, request.context)
        return QueryResponse(response=response, success=True)
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/health", response_model=HealthAnalysisResponse)
async def analyze_health(request: HealthAnalysisRequest, req: Request) -> HealthAnalysisResponse:
    """Analyze device health data from n8n workflow.

    This endpoint is called by the Unifi Health to Slack workflow
    to get AI-powered analysis and recommendations.
    """
    agent = getattr(req.app.state, "agent", None)
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        analysis = await agent.analyze_health(request.devices, request.summary)
        return HealthAnalysisResponse(analysis=analysis, success=True)
    except Exception as e:
        logger.error(f"Health analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/audit", response_model=AuditAnalysisResponse)
async def analyze_audit(request: AuditAnalysisRequest, req: Request) -> AuditAnalysisResponse:
    """Analyze security audit results from n8n workflow.

    This endpoint is called by the Unifi Best Practices Audit workflow
    to get AI-powered remediation recommendations.
    """
    agent = getattr(req.app.state, "agent", None)
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        recommendations = await agent.analyze_audit(
            findings=request.findings,
            networks=request.networks,
            wlans=request.wlans,
            firewall_rules=request.firewall_rules,
            devices=request.devices,
        )
        return AuditAnalysisResponse(recommendations=recommendations, success=True)
    except Exception as e:
        logger.error(f"Audit analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(request: KnowledgeSearchRequest, req: Request) -> KnowledgeSearchResponse:
    """Search the knowledge base directly.

    Useful for testing or building custom integrations.
    """
    kb = getattr(req.app.state, "knowledge_base", None)
    if not kb:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    try:
        results = await kb.search(request.query, request.n_results)
        return KnowledgeSearchResponse(results=results, success=True)
    except Exception as e:
        logger.error(f"Knowledge search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/stats")
async def knowledge_stats(req: Request) -> dict[str, Any]:
    """Get knowledge base statistics."""
    kb = getattr(req.app.state, "knowledge_base", None)
    if not kb:
        return {"status": "not initialized"}

    return kb.get_stats()
