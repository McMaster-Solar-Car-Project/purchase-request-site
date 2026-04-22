from datetime import datetime

from src.app_factory import create_app
from src.core.logging_utils import setup_logger
from src.core.settings import get_settings

app = create_app()
logger = setup_logger(__name__)
settings = get_settings()


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server at {datetime.now().isoformat()}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=False,
    )
