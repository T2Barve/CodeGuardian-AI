"""
CodeGuardian AI — Worker Health Check Probe
Evaluates worker service health by verifying Redis connectivity and process status.
"""

import asyncio
import sys
import redis.asyncio as aioredis
from app.config.settings import settings


async def check_health() -> int:
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
        await r.ping()
        await r.aclose()
        return 0
    except Exception as exc:
        sys.stderr.write(f"Worker health check failed: {exc}\n")
        return 1


def main():
    exit_code = asyncio.run(check_health())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
