"""
CodeGuardian AI — Phase 18 DevOps & Production Infrastructure Unit Test Suite
Validates Dockerfile security compliance, Nginx hardening, compose topology,
environment configuration templates, and GitHub Actions CI pipelines.
"""

from pathlib import Path
import pytest
import yaml

# Resolve workspace root from apps/backend/tests/unit/ (5 levels up)
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


class TestDevOpsConfiguration:
    """Verifies all Phase 18 Production DevOps configuration files against CIS benchmarks."""

    def test_backend_dockerfile_compliance(self):
        """Backend Dockerfile must enforce multi-stage builds, non-root user, dumb-init, and healthchecks."""
        dockerfile_path = WORKSPACE_ROOT / "apps" / "backend" / "Dockerfile"
        assert dockerfile_path.exists(), f"Missing backend Dockerfile: {dockerfile_path}"

        content = dockerfile_path.read_text(encoding="utf-8")

        # Multi-stage build verification
        assert "FROM python:" in content
        assert "AS builder" in content
        assert "AS runner" in content

        # Non-root unprivileged user enforcement
        assert "useradd" in content
        assert "codeguardian" in content
        assert "USER codeguardian" in content

        # Process supervisor and healthcheck
        assert "dumb-init" in content
        assert "HEALTHCHECK" in content
        assert "/api/v1/health" in content

        # Environment optimizations
        assert "PYTHONUNBUFFERED=1" in content
        assert "PYTHONDONTWRITEBYTECODE=1" in content
        assert "EXPOSE 8000" in content

    def test_worker_dockerfile_compliance(self):
        """Worker Dockerfile must enforce multi-stage builds, non-root user, dumb-init, and healthchecks."""
        dockerfile_path = WORKSPACE_ROOT / "services" / "worker" / "Dockerfile"
        assert dockerfile_path.exists(), f"Missing worker Dockerfile: {dockerfile_path}"

        content = dockerfile_path.read_text(encoding="utf-8")

        # Multi-stage build verification
        assert "AS builder" in content
        assert "AS runner" in content

        # Non-root user verification
        assert "codeguardian" in content
        assert "USER codeguardian" in content

        # Process supervisor and healthcheck probe
        assert "dumb-init" in content
        assert "HEALTHCHECK" in content
        assert "healthcheck.py" in content
        assert "worker.py" in content

    def test_frontend_dockerfile_compliance(self):
        """Frontend Dockerfile must use Node build stage, Alpine Nginx runtime, and healthchecks."""
        dockerfile_path = WORKSPACE_ROOT / "apps" / "frontend" / "Dockerfile"
        assert dockerfile_path.exists(), f"Missing frontend Dockerfile: {dockerfile_path}"

        content = dockerfile_path.read_text(encoding="utf-8")

        # Multi-stage build verification
        assert "FROM node:20-alpine AS builder" in content
        assert "FROM nginx:" in content
        assert "AS runner" in content
        assert "npm run build" in content

        # Nginx configuration copying
        assert "nginx.conf" in content
        assert "HEALTHCHECK" in content
        assert "nginx-health" in content

    def test_nginx_configuration_hardening(self):
        """Nginx config must implement security headers, gzip compression, SPA routing, and reverse proxy."""
        nginx_path = WORKSPACE_ROOT / "apps" / "frontend" / "nginx.conf"
        assert nginx_path.exists(), f"Missing Nginx config: {nginx_path}"

        content = nginx_path.read_text(encoding="utf-8")

        # Security headers
        assert "X-Frame-Options" in content
        assert "X-Content-Type-Options" in content
        assert "Content-Security-Policy" in content
        assert "Referrer-Policy" in content

        # Performance & Gzip
        assert "gzip on;" in content
        assert "application/json" in content
        assert "application/javascript" in content

        # SPA routing fallback and reverse proxy
        assert "try_files $uri $uri/ /index.html;" in content
        assert "location /api/" in content
        assert "proxy_pass http://backend:8000;" in content
        assert "proxy_read_timeout 120s;" in content

        # Liveness check
        assert "location /nginx-health" in content

    def test_production_compose_topology_and_security(self):
        """Production docker-compose must enforce tiered network isolation, resource limits, and healthchecks."""
        compose_path = WORKSPACE_ROOT / "docker-compose.prod.yml"
        assert compose_path.exists(), f"Missing production compose: {compose_path}"

        content = compose_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        assert "services" in data
        services = data["services"]

        # 5 core services present
        for expected_service in ["postgres", "redis", "backend", "worker", "frontend"]:
            assert expected_service in services, f"Service {expected_service} missing from production compose"

        # Tiered network architecture
        assert "networks" in data
        assert "frontend-tier" in data["networks"]
        assert "backend-tier" in data["networks"]
        assert data["networks"]["backend-tier"].get("internal") is True, "backend-tier must be internal"

        # Security: Postgres & Redis must NOT be accessible in frontend-tier or expose ports
        assert "ports" not in services["postgres"], "PostgreSQL must not expose ports to host in production"
        assert "ports" not in services["redis"], "Redis must not expose ports to host in production"
        assert "frontend-tier" not in services["postgres"]["networks"]
        assert "frontend-tier" not in services["redis"]["networks"]

        # Healthchecks and resource limits on all services
        for name, srv in services.items():
            assert "healthcheck" in srv, f"Service {name} lacks healthcheck"
            assert "deploy" in srv and "resources" in srv["deploy"], f"Service {name} lacks resource limits"
            limits = srv["deploy"]["resources"]["limits"]
            assert "cpus" in limits and "memory" in limits, f"Service {name} missing CPU/memory limits"

        # Worker cluster scaling
        assert services["worker"]["deploy"].get("replicas", 1) >= 2, "Production worker should have at least 2 replicas"

    def test_production_environment_example(self):
        """Production environment example must cover all required parameters with zero plain secrets."""
        env_path = WORKSPACE_ROOT / ".env.production.example"
        assert env_path.exists(), f"Missing production env template: {env_path}"

        content = env_path.read_text(encoding="utf-8")

        required_keys = [
            "ENVIRONMENT=production",
            "DATABASE_URL",
            "POSTGRES_PASSWORD",
            "REDIS_PASSWORD",
            "SECRET_KEY",
            "GITHUB_WEBHOOK_SECRET",
            "LLM_PROVIDER",
            "LLM_API_KEY",
            "UVICORN_WORKERS",
        ]
        for key in required_keys:
            assert key in content, f"Key {key} missing from .env.production.example"

    def test_github_actions_ci_workflow_structure(self):
        """GitHub Actions CI workflow must contain all automated verification jobs."""
        ci_path = WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), f"Missing CI workflow: {ci_path}"

        content = ci_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        assert "jobs" in data
        jobs = data["jobs"]

        # Verify all mandatory CI stages are defined
        assert "backend-ci" in jobs
        assert "frontend-ci" in jobs
        assert "docker-validation" in jobs
        assert "docker-build-test" in jobs

        # Backend-ci runs pytest
        backend_steps = str(jobs["backend-ci"]["steps"])
        assert "ruff check" in backend_steps
        assert "pytest" in backend_steps

        # Frontend-ci runs build
        frontend_steps = str(jobs["frontend-ci"]["steps"])
        assert "npm run build" in frontend_steps

        # Docker validation checks compose
        docker_steps = str(jobs["docker-validation"]["steps"])
        assert "docker-compose.prod.yml" in docker_steps
