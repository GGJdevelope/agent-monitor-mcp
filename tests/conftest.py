import pytest
import os
import tempfile
from httpx import AsyncClient, ASGITransport
from app.repositories.status_repository import StatusRepository
from app.services.status_service import StatusService
from app.main import app as main_app
from app import mcp_server

@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture(autouse=True)
def reset_mcp_singleton():
    """Reset the MCP server singleton before each test."""
    mcp_server._status_service = None
    yield
    mcp_server._status_service = None

@pytest.fixture
def repository(db_path):
    repo = StatusRepository(db_path)
    repo._init_db()
    return repo

@pytest.fixture
def service(repository):
    return StatusService(repository)

@pytest.fixture
def app(service):
    # Setup the app state for testing
    main_app.state.status_service = service
    return main_app

@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
