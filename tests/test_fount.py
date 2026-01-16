"""Tests for Phase 7: Fount Client."""

import pytest
from pathlib import Path
from sunwell.fount.client import FountClient
from sunwell.fount.cache import FountCache
from sunwell.fount.resolver import LensResolver
from sunwell.schema.loader import LensLoader
from sunwell.core.types import LensReference, SunwellError

@pytest.fixture
def lens_loader(fount_client):
    return LensLoader(fount_client=fount_client)

@pytest.fixture
def lens_resolver(lens_loader):
    return LensResolver(loader=lens_loader)

@pytest.mark.asyncio
async def test_lens_resolver_merging(lens_resolver, fount_client):
    """Test that LensResolver correctly merges inherited heuristics."""
    # Mock a child lens that extends sunwell/base-writer
    child_content = """
lens:
  metadata:
    name: "Child Writer"
  extends: "sunwell/base-writer"
  heuristics:
    - name: "Child Rule"
      rule: "Add more details"
"""
    # Force the mock fetch to return this for a specific name
    async def custom_mock_fetch(source, version=None):
        if source == "sunwell/base-writer":
            return """
lens:
  metadata:
    name: "Base Writer"
  heuristics:
    - name: "Base Rule"
      rule: "Be concise"
"""
        return child_content
    
    fount_client._mock_fetch = custom_mock_fetch
    
    ref = LensReference(source="child-lens")
    resolved = await lens_resolver.resolve(ref)
    
    assert resolved.metadata.name == "Child Writer"
    # Should have both base and child heuristics
    h_names = {h.name for h in resolved.heuristics}
    assert "Base Rule" in h_names
    assert "Child Rule" in h_names

@pytest.mark.asyncio
async def test_lens_resolver_circular(lens_resolver, fount_client):
    """Test that LensResolver detects circular dependencies."""
    async def circular_mock_fetch(source, version=None):
        return f"""
lens:
  metadata:
    name: "{source}"
  extends: "{'a' if source == 'b' else 'b'}"
"""
    fount_client._mock_fetch = circular_mock_fetch
    
    with pytest.raises(SunwellError) as excinfo:
        await lens_resolver.resolve(LensReference(source="a"))
    assert "circular dependency" in str(excinfo.value).lower()

@pytest.fixture
def tmp_fount_cache(tmp_path: Path):
    return FountCache(root=tmp_path / "fount_cache")

@pytest.fixture
def fount_client(tmp_fount_cache):
    return FountClient(cache=tmp_fount_cache)

@pytest.mark.asyncio
async def test_fount_client_fetch_mock(fount_client):
    """Test fetching a mocked lens from the fount."""
    content = await fount_client.fetch("sunwell/base-writer")
    assert "Base Writer" in content
    assert "Signal over Noise" in content

@pytest.mark.asyncio
async def test_fount_client_cache(fount_client, tmp_fount_cache):
    """Test that fetched lenses are cached locally."""
    ref = LensReference(source="sunwell/base-writer")
    
    # Initially not in cache
    assert tmp_fount_cache.get(ref) is None
    
    # Fetch it
    await fount_client.fetch("sunwell/base-writer")
    
    # Should now be in cache
    assert tmp_fount_cache.get(ref) is not None
    assert "Base Writer" in tmp_fount_cache.get(ref)

@pytest.mark.asyncio
async def test_fount_client_not_found(fount_client):
    """Test error handling when a lens is not found."""
    with pytest.raises(SunwellError) as excinfo:
        await fount_client.fetch("nonexistent/lens")
    assert "not found" in str(excinfo.value).lower()
