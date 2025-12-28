"""Main entry point for the UniFi Expert Agent service."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .agent.core import UniFiExpertAgent
from .api.routes import router
from .config import settings
from .knowledge.embeddings import KnowledgeBase
from .slack.handler import start_slack_handler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting UniFi Expert Agent service...")

    # Initialize knowledge base
    kb = KnowledgeBase()
    try:
        await kb.initialize()
        app.state.knowledge_base = kb
        logger.info("Knowledge base initialized")
    except Exception as e:
        logger.warning(f"Knowledge base initialization failed: {e}")
        logger.warning("Continuing without knowledge base...")
        app.state.knowledge_base = None

    # Initialize agent
    agent = UniFiExpertAgent(knowledge_base=kb)
    app.state.agent = agent
    logger.info("Agent initialized")

    # Start Slack handler in background
    slack_task = None
    if settings.SLACK_APP_TOKEN and settings.SLACK_BOT_TOKEN:
        logger.info("Starting Slack Socket Mode handler...")
        slack_task = asyncio.create_task(start_slack_handler(agent))
    else:
        logger.warning("Slack tokens not configured, Slack integration disabled")

    yield

    # Cleanup
    logger.info("Shutting down...")

    if slack_task:
        slack_task.cancel()
        try:
            await slack_task
        except asyncio.CancelledError:
            pass

    await agent.close()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="UniFi Expert Agent",
    description="AI-powered UniFi network expert with Slack integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routes
app.include_router(router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "UniFi Expert Agent",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "ready": "/api/ready",
            "query": "/api/query",
            "analyze_health": "/api/analyze/health",
            "analyze_audit": "/api/analyze/audit",
            "knowledge_search": "/api/knowledge/search",
            "knowledge_stats": "/api/knowledge/stats",
        },
    }


def main():
    """Run the application."""
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
