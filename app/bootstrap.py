from datetime import datetime, timezone, timedelta
import logging
from app.config import settings
from app.repositories.status_repository import StatusRepository
from app.services.status_service import StatusService

logger = logging.getLogger(__name__)

def bootstrap_service() -> StatusService:
    """
    Common bootstrap logic for both MCP and FastAPI.
    Initializes repository, prunes old data, and creates StatusService.
    """
    logger.info(f"Initializing StatusRepository with {settings.DATABASE_URL}")
    repository = StatusRepository(settings.DATABASE_URL)
    
    if settings.STATUS_RETENTION_SECONDS > 0:
        logger.info(f"Starting startup retention cleanup ({settings.STATUS_RETENTION_SECONDS}s)")
        try:
            # bootstrap computes a UTC cutoff datetime from retention seconds
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=settings.STATUS_RETENTION_SECONDS)
            
            results = repository.prune_expired_data(cutoff)
            logger.info(f"Cleanup complete: pruned {results['deleted_events']} events, {results['deleted_snapshots']} snapshots")
        except Exception as e:
            logger.error(f"Failed to perform startup cleanup: {e}")
            # Fail fast on cleanup SQL errors; do not silently ignore them.
            raise
    else:
        logger.info("Startup retention cleanup is disabled (STATUS_RETENTION_SECONDS=0)")

    service = StatusService(
        repository, 
        stale_threshold_seconds=settings.STALE_THRESHOLD_SECONDS
    )
    return service
