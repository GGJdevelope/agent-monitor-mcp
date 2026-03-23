import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_dashboard_has_dark_mode_structure(client: AsyncClient):
    """
    Validates that the dashboard root HTML includes the dark mode structure
    without brittle UI assertions.
    """
    response = await client.get("/")
    assert response.status_code == 200
    
    html = response.text
    
    # Check for Tailwind config with darkMode: 'class'
    assert "darkMode: 'class'" in html
    
    # Check for the theme initialization script (prefers-color-scheme)
    assert "localStorage.getItem('dashboard-theme')" in html
    assert "window.matchMedia('(prefers-color-scheme: dark)')" in html
    
    # Check for the theme toggle button and icons
    assert 'id="theme-toggle"' in html
    assert 'id="sun-icon"' in html
    assert 'id="moon-icon"' in html
    
    # Check for some key dark mode classes
    assert 'dark:bg-gray-900' in html
    assert 'dark:text-gray-100' in html
    assert 'dark:border-gray-700' in html

@pytest.mark.asyncio
async def test_dashboard_scripts_loaded(client: AsyncClient):
    """
    Ensures essential scripts for the dashboard are present.
    """
    response = await client.get("/")
    assert response.status_code == 200
    
    html = response.text
    assert "function renderAgents()" in html
    assert "function connectSSE()" in html
    assert 'src="https://cdn.tailwindcss.com"' in html
