"""Tests for Phase 7: Fount Client (RFC-094: Cache integrity)."""

import json
import threading

import pytest
from pathlib import Path
from sunwell.features.fount.client import FountClient
from sunwell.features.fount.cache import FountCache
from sunwell.features.fount.resolver import LensResolver
from sunwell.foundation.schema.loader.loader import LensLoader
from sunwell.foundation.errors import SunwellError
from sunwell.core.types.types import LensReference

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
    async def custom_fetch(source, version=None):
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
    
    # Use the _mock_fetch_override field for testing
    fount_client._mock_fetch_override = custom_fetch
    
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
    fount_client._mock_fetch_override = circular_mock_fetch
    
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


# =============================================================================
# RFC-094: FountCache Integrity & Thread-Safety Tests
# =============================================================================


class TestFountCacheIntegrity:
    """Tests for FountCache content integrity verification (RFC-094)."""

    def test_cache_stores_content_hash(self, tmp_path):
        """Cache should store content hash in metadata."""
        cache = FountCache(root=tmp_path / "cache")
        ref = LensReference(source="test/lens", version="1.0")
        
        cache.set(ref, "lens: content here")
        
        # Check metadata file has content_hash
        meta_path = cache._get_metadata_path(ref)
        assert meta_path.exists()
        
        meta = json.loads(meta_path.read_text())
        assert "content_hash" in meta
        assert len(meta["content_hash"]) == 32  # BLAKE2b digest_size=16 → 32 hex chars

    def test_cache_detects_corruption(self, tmp_path):
        """Cache should return None for corrupted content."""
        cache = FountCache(root=tmp_path / "cache")
        ref = LensReference(source="test/lens", version="1.0")
        
        # Store valid content
        cache.set(ref, "valid: content")
        
        # Verify it's retrievable
        assert cache.get(ref) == "valid: content"
        
        # Corrupt the file
        cache._get_lens_path(ref).write_text("corrupted!")
        
        # Should return None (not corrupted content)
        assert cache.get(ref) is None
        
        # File should be deleted after corruption detection
        assert not cache._get_lens_path(ref).exists()
        assert not cache._get_metadata_path(ref).exists()

    def test_cache_works_without_metadata(self, tmp_path):
        """Cache should still work if metadata is missing (legacy entries)."""
        cache = FountCache(root=tmp_path / "cache")
        ref = LensReference(source="test/lens", version="1.0")
        
        # Manually write lens file without metadata
        lens_path = cache._get_lens_path(ref)
        lens_path.parent.mkdir(parents=True, exist_ok=True)
        lens_path.write_text("legacy: content")
        
        # Should still be retrievable (no verification possible)
        assert cache.get(ref) == "legacy: content"

    def test_cache_handles_corrupted_metadata(self, tmp_path):
        """Cache should handle corrupted metadata gracefully."""
        cache = FountCache(root=tmp_path / "cache")
        ref = LensReference(source="test/lens", version="1.0")
        
        cache.set(ref, "valid: content")
        
        # Corrupt metadata
        cache._get_metadata_path(ref).write_text("not json!")
        
        # Should still return content (metadata parse fails gracefully)
        assert cache.get(ref) == "valid: content"

    def test_cache_clear_removes_all(self, tmp_path):
        """Clear should remove all cached content."""
        cache = FountCache(root=tmp_path / "cache")
        
        ref1 = LensReference(source="test/lens1", version="1.0")
        ref2 = LensReference(source="test/lens2", version="1.0")
        
        cache.set(ref1, "content1")
        cache.set(ref2, "content2")
        
        cache.clear()
        
        assert cache.get(ref1) is None
        assert cache.get(ref2) is None


class TestFountCacheThreadSafety:
    """Tests for FountCache thread safety (RFC-094)."""

    def test_cache_has_lock(self, tmp_path):
        """Cache should have a threading lock."""
        cache = FountCache(root=tmp_path / "cache")
        assert hasattr(cache, "_lock")
        assert isinstance(cache._lock, type(threading.Lock()))

    def test_concurrent_writes(self, tmp_path):
        """Concurrent writes should not corrupt cache."""
        cache = FountCache(root=tmp_path / "cache")
        errors: list[Exception] = []
        
        def writer(i: int) -> None:
            try:
                ref = LensReference(source=f"test/lens-{i}", version="1.0")
                cache.set(ref, f"content-{i}")
            except Exception as e:
                errors.append(e)
        
        # Launch concurrent writers
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors, f"Thread-safety errors: {errors}"
        
        # Verify all entries are valid
        for i in range(20):
            ref = LensReference(source=f"test/lens-{i}", version="1.0")
            content = cache.get(ref)
            assert content == f"content-{i}", f"Wrong content for lens-{i}"

    def test_concurrent_reads_writes(self, tmp_path):
        """Concurrent reads and writes should not corrupt cache."""
        cache = FountCache(root=tmp_path / "cache")
        errors: list[Exception] = []
        
        # Pre-populate some entries
        for i in range(10):
            ref = LensReference(source=f"test/lens-{i}", version="1.0")
            cache.set(ref, f"content-{i}")
        
        def writer(i: int) -> None:
            try:
                ref = LensReference(source=f"test/lens-{i + 10}", version="1.0")
                cache.set(ref, f"content-{i + 10}")
            except Exception as e:
                errors.append(e)
        
        def reader(i: int) -> None:
            try:
                ref = LensReference(source=f"test/lens-{i % 10}", version="1.0")
                result = cache.get(ref)
                # Result should be valid content or None (if cleared/corrupted)
                if result is not None:
                    assert result == f"content-{i % 10}"
            except Exception as e:
                errors.append(e)
        
        # Launch concurrent readers and writers
        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors, f"Thread-safety errors: {errors}"

    def test_concurrent_clear(self, tmp_path):
        """Concurrent clear should not cause errors."""
        cache = FountCache(root=tmp_path / "cache")
        errors: list[Exception] = []
        
        def writer_clearer(i: int) -> None:
            try:
                if i % 3 == 0:
                    cache.clear()
                else:
                    ref = LensReference(source=f"test/lens-{i}", version="1.0")
                    cache.set(ref, f"content-{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer_clearer, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors, f"Thread-safety errors during clear: {errors}"
