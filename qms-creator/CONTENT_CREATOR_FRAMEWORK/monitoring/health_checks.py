"""
Enhanced health check endpoints for Cannabis EU GMP QMS Creator.

Provides comprehensive system health monitoring including database, external services,
file system, and memory checks.
"""

import logging
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import psutil
from sqlalchemy import text

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Represents health status of a single component."""

    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize component health.

        Args:
            name: Component name
            status: Health status
            message: Status message
            details: Additional details
        """
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


class HealthChecker:
    """Comprehensive health checker for all system components."""

    def __init__(self, db_session=None, ollamqa_url: Optional[str] = None):
        """
        Initialize health checker.

        Args:
            db_session: SQLAlchemy database session
            ollama_url: Ollama API URL
        """
        self.db_session = db_session
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL")
        self.components: List[ComponentHealth] = []

    async def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with overall health status and component details
        """
        self.components = []

        # Run all checks
        await self._check_application()
        await self._check_database()
        await self._check_file_system()
        await self._check_memory()
        await self._check_disk_space()
        await self._check_external_services()

        # Determine overall status
        overall_status = self._determine_overall_status()

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "components": [c.to_dict() for c in self.components],
            "summary": self._get_summary(),
        }

    async def _check_application(self) -> None:
        """Check application status."""
        try:
            self.components.append(
                ComponentHealth(
                    "application",
                    HealthStatus.HEALTHY,
                    "Application is running",
                    {"pid": os.getpid()},
                )
            )
        except Exception as e:
            logger.error(f"Application health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "application",
                    HealthStatus.UNHEALTHY,
                    str(e),
                )
            )

    async def _check_database(self) -> None:
        """Check database connectivity and performance."""
        if not self.db_session:
            logger.warning("No database session provided, skipping database check")
            return

        try:
            # Test connection
            result = self.db_session.execute(text("SELECT 1"))
            result.fetchone()

            # Get pool stats
            pool = self.db_session.get_bind().pool
            pool_size = pool.size() if hasattr(pool, "size") else 0
            checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0

            self.components.append(
                ComponentHealth(
                    "database",
                    HealthStatus.HEALTHY,
                    "Database connection successful",
                    {
                        "type": "PostgreSQL",
                        "pool_size": pool_size,
                        "checked_out": checked_out,
                    },
                )
            )
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "database",
                    HealthStatus.UNHEALTHY,
                    f"Database connection failed: {str(e)}",
                )
            )

    async def _check_file_system(self) -> None:
        """Check file system access and permissions."""
        try:
            paths_to_check = {
                "data": "data/",
                "output": "output/",
                "logs": "logs/",
                "uploads": "uploads/",
            }

            accessible_paths = {}
            issues = []

            for name, path in paths_to_check.items():
                if os.path.exists(path):
                    is_writable = os.access(path, os.W_OK)
                    accessible_paths[name] = {
                        "exists": True,
                        "writable": is_writable,
                    }
                    if not is_writable:
                        issues.append(f"{name} is not writable")
                else:
                    # Try to create directory
                    try:
                        os.makedirs(path, exist_ok=True)
                        accessible_paths[name] = {
                            "exists": True,
                            "writable": True,
                        }
                    except Exception:
                        accessible_paths[name] = {
                            "exists": False,
                            "writable": False,
                        }
                        issues.append(f"Cannot access {name}")

            status = HealthStatus.HEALTHY if not issues else HealthStatus.DEGRADED
            message = (
                "File system check passed"
                if not issues
                else f"Issues: {'; '.join(issues)}"
            )

            self.components.append(
                ComponentHealth(
                    "file_system",
                    status,
                    message,
                    {"paths": accessible_paths},
                )
            )
        except Exception as e:
            logger.error(f"File system health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "file_system",
                    HealthStatus.DEGRADED,
                    str(e),
                )
            )

    async def _check_memory(self) -> None:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)

            status = HealthStatus.HEALTHY
            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
            elif memory.percent > 80:
                status = HealthStatus.DEGRADED

            self.components.append(
                ComponentHealth(
                    "memory",
                    status,
                    f"Memory usage: {memory.percent}%",
                    {
                        "total_gb": round(memory.total / (1024**3), 2),
                        "used_gb": round(memory.used / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "percent": memory.percent,
                        "cpu_percent": cpu_percent,
                    },
                )
            )
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "memory",
                    HealthStatus.DEGRADED,
                    str(e),
                )
            )

    async def _check_disk_space(self) -> None:
        """Check disk space."""
        try:
            disk = psutil.disk_usage("/")

            status = HealthStatus.HEALTHY
            if disk.percent > 90:
                status = HealthStatus.UNHEALTHY
            elif disk.percent > 80:
                status = HealthStatus.DEGRADED

            self.components.append(
                ComponentHealth(
                    "disk_space",
                    status,
                    f"Disk usage: {disk.percent}%",
                    {
                        "total_gb": round(disk.total / (1024**3), 2),
                        "used_gb": round(disk.used / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "percent": disk.percent,
                    },
                )
            )
        except Exception as e:
            logger.error(f"Disk space health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "disk_space",
                    HealthStatus.DEGRADED,
                    str(e),
                )
            )

    async def _check_external_services(self) -> None:
        """Check external services (Ollama, OpenAI, etc.)."""
        try:
            import aiohttp

            services_to_check = {}

            # Check Ollama
            if self.ollama_url:
                services_to_check["ollama"] = f"{self.ollama_url}/api/tags"

            # Check OpenAI (basic check)
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                services_to_check["openai"] = ("configured", openai_key is not None)

            # Check Anthropic (basic check)
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            if anthropic_key:
                services_to_check["anthropic"] = (
                    "configured",
                    anthropic_key is not None,
                )

            service_statuses = {}

            async with aiohttp.ClientSession() as session:
                for service_name, url in services_to_check.items():
                    if isinstance(url, tuple):
                        # Simple check for API keys
                        service_statuses[service_name] = {
                            "status": "configured",
                            "available": url[1],
                        }
                    else:
                        try:
                            async with session.get(url, timeout=5) as resp:
                                service_statuses[service_name] = {
                                    "status": "available"
                                    if resp.status == 200
                                    else "unavailable",
                                    "status_code": resp.status,
                                }
                        except Exception as e:
                            service_statuses[service_name] = {
                                "status": "unavailable",
                                "error": str(e),
                            }

            overall_status = (
                HealthStatus.HEALTHY
                if all(
                    s.get("status") in ["available", "configured"]
                    for s in service_statuses.values()
                )
                else HealthStatus.DEGRADED
            )

            self.components.append(
                ComponentHealth(
                    "external_services",
                    overall_status,
                    "External services check completed",
                    service_statuses,
                )
            )
        except Exception as e:
            logger.error(f"External services health check failed: {e}")
            self.components.append(
                ComponentHealth(
                    "external_services",
                    HealthStatus.DEGRADED,
                    str(e),
                )
            )

    def _determine_overall_status(self) -> HealthStatus:
        """Determine overall system health status."""
        if not self.components:
            return HealthStatus.HEALTHY

        # If any component is unhealthy, system is unhealthy
        if any(c.status == HealthStatus.UNHEALTHY for c in self.components):
            return HealthStatus.UNHEALTHY

        # If any component is degraded, system is degraded
        if any(c.status == HealthStatus.DEGRADED for c in self.components):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _get_summary(self) -> Dict[str, int]:
        """Get summary of component health statuses."""
        summary = {
            "total": len(self.components),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
        }

        for component in self.components:
            if component.status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif component.status == HealthStatus.DEGRADED:
                summary["degraded"] += 1
            elif component.status == HealthStatus.UNHEALTHY:
                summary["unhealthy"] += 1

        return summary


# Convenience function
async def check_health(
    db_session=None, ollama_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform comprehensive health check.

    Args:
        db_session: SQLAlchemy database session
        ollama_url: Ollama API URL

    Returns:
        Health check results
    """
    checker = HealthChecker(db_session=db_session, ollamqa_url=ollama_url)
    return await checker.check_all()
