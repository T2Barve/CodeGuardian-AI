from fastapi import APIRouter
from app.api.v1.endpoints import (
    agents,
    audit,
    auth,
    dashboard,
    findings,
    github,
    health,
    integrations,
    metrics,
    optimization,
    policies,
    pull_requests,
    queue,
    rag,
    remediation,
    reports,
    repositories,
    risk,
    scanners,
)

api_router = APIRouter()

# Include endpoint groups
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(health.router, tags=["Health & Observability"])
api_router.include_router(dashboard.router, tags=["Dashboard & Metrics"])
api_router.include_router(repositories.router, tags=["Repositories"])
api_router.include_router(pull_requests.router, tags=["Pull Requests"])
api_router.include_router(github.router, tags=["GitHub Integration"])
api_router.include_router(queue.router, tags=["Queue & Workers"])
api_router.include_router(findings.router, tags=["Reviews & Findings"])
api_router.include_router(risk.router, tags=["Risk Engine & Scoring"])
api_router.include_router(agents.router, tags=["Multi-Agent Orchestration"])
api_router.include_router(scanners.router, tags=["Scanner Center"])
api_router.include_router(integrations.router, tags=["Integrations"])
api_router.include_router(policies.router, tags=["Engineering Policies"])
api_router.include_router(rag.router, tags=["Policy RAG Engine"])
api_router.include_router(reports.router, tags=["Review Reports & Synthesis"])
api_router.include_router(remediation.router, tags=["Remediation Engine"])
api_router.include_router(metrics.router, tags=["Performance & Evaluation Metrics"])
api_router.include_router(optimization.router, tags=["NLP Code Optimization & Complexity Engine"])
api_router.include_router(audit.router, tags=["Audit & Compliance"])



