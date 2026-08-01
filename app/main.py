from fastapi import FastAPI

from app.api.routes.delivery import router as delivery_router
from app.api.routes.emails import router as emails_router
from app.api.routes.health import router as health_router
from app.api.routes.inbox import router as inbox_router
from app.api.routes.replies import router as replies_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    application.include_router(health_router)
    application.include_router(inbox_router)
    application.include_router(emails_router)
    application.include_router(replies_router)
    application.include_router(delivery_router)
    return application


app = create_app()
