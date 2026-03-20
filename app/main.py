from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.bootstrap import bootstrap_service
from app.api import status as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure DB is ready and prune old data via bootstrap
    service = bootstrap_service()
    
    # Store service in app state
    app.state.status_service = service
    yield

app = FastAPI(title="Agent Monitor", lifespan=lifespan)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router.router, prefix="/api", tags=["status"])

# Dashboard
templates = Jinja2Templates(directory="app/dashboard/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
