"""Tests for RFC-023: Adaptive Identity module."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from sunwell.core.models.heuristic import Identity
from sunwell.identity.core.models import Observation
from sunwell.identity.store import IdentityStore
from sunwell.identity.extractor import extract_behaviors_regex, _TWO_TIER_EXTRACTION_PROMPT
from sunwell.identity.digest import _extract_confidence, _extract_prompt, quick_digest
from sunwell.identity.injection import build_system_prompt_with_identity
from sunwell.planning.naaru.persona import MURU, NaaruPersona


class TestNaaruPersona:
    """Tests for M'uru's persona configuration."""
    
    def test_muru_name(self):
        assert MURU.name == "M'uru"
    
    def test_msg_noted(self):
        msg = MURU.msg_noted("User has a cat")
        # Should contain one of the titles (alternates)
        assert "noted" in msg
        assert ("M'uru" in msg or "The Naaru" in msg or "The Light" in msg)
        assert "User has a cat" in msg
    
    def test_msg_observed(self):
        msg = MURU.msg_observed("Uses casual language")
        assert "observed" in msg
        assert ("M'uru" in msg or "The Naaru" in msg or "The Light" in msg)
        assert "Uses casual language" in msg
    
    def test_msg_observed_truncation(self):
        long_behavior = "A" * 100
        msg = MURU.msg_observed(long_behavior, truncate=30)
        assert "..." in msg
        assert "observed" in msg
    
    def test_msg_learned(self):
        msg = MURU.msg_learned("API timeout is 5 seconds")
        assert "learned" in msg
        assert ("M'uru" in msg or "The Naaru" in msg or "The Light" in msg)
        assert "API timeout" in msg
    
    def test_msg_identity_updated(self):
        msg = MURU.msg_identity_updated(0.85)
        # Alternates between M'uru, The Naaru, and The Light (per project config)
        assert ("M'uru" in msg or "The Naaru" in msg or "The Light" in msg)
        assert "85%" in msg
    
    def test_msg_error(self):
        # Error messages always use the name (not alternating titles)
        msg = MURU.msg_error("extraction", "Connection failed")
        assert MURU.name in msg  # Should be M'uru
        assert "extraction failed" in msg
        assert "Connection failed" in msg
    
    def test_alternating_titles(self):
        """Messages should alternate between titles."""
        persona = NaaruPersona(
            name="M'uru",
            titles=["M'uru", "The Naaru"],
            alternate=True,
        )
        
        msg1 = persona.msg_noted("fact 1")
        msg2 = persona.msg_noted("fact 2")
        
        # Should use different titles
        # (counter starts at 0, first call increments to 1, second to 2)
        assert ("M'uru" in msg1 and "The Naaru" in msg2) or ("The Naaru" in msg1 and "M'uru" in msg2)
    
    def test_no_alternation(self):
        """With alternate=False, should always use name."""
        persona = NaaruPersona(
            name="M'uru",
            titles=["M'uru", "The Naaru"],
            alternate=False,
        )
        
        msg1 = persona.msg_noted("fact 1")
        msg2 = persona.msg_noted("fact 2")
        
        # Should always use name
        assert "M'uru" in msg1
        assert "M'uru" in msg2


class TestObservation:
    """Tests for Observation dataclass."""
    
    def test_observation_creation(self):
        obs = Observation(
            timestamp=datetime.now(),
            observation="Uses casual language",
            confidence=0.8,
        )
        assert obs.observation == "Uses casual language"
        assert obs.confidence == 0.8
    
    def test_observation_serialization(self):
        now = datetime.now()
        obs = Observation(
            timestamp=now,
            observation="Test observation",
            confidence=0.9,
            turn_id="turn123",
        )
        
        data = obs.to_dict()
        assert data["observation"] == "Test observation"
        assert data["confidence"] == 0.9
        assert data["turn_id"] == "turn123"
        
        # Deserialize
        restored = Observation.from_dict(data)
        assert restored.observation == obs.observation
        assert restored.confidence == obs.confidence
        assert restored.turn_id == obs.turn_id


class TestIdentity:
    """Tests for Identity dataclass."""
    
    def test_identity_creation(self):
        identity = Identity()
        assert identity.observations == []
        assert identity.prompt is None
        assert identity.confidence == 0.0
        assert not identity.is_usable()
    
    def test_identity_usable(self):
        """Identity is usable when prompt exists and confidence >= 0.6."""
        identity = Identity(
            prompt="This user prefers casual interaction.",
            confidence=0.7,
        )
        assert identity.is_usable()
        
        # Below confidence threshold
        identity.confidence = 0.5
        assert not identity.is_usable()
        
        # No prompt
        identity = Identity(confidence=0.8)
        assert not identity.is_usable()
    
    def test_identity_serialization(self):
        identity = Identity(
            observations=[
                Observation(datetime.now(), "Casual language", 0.8),
                Observation(datetime.now(), "Appreciative", 0.9),
            ],
            tone="casual",
            values=["being remembered", "efficiency"],
            prompt="User prefers casual interaction.",
            confidence=0.85,
        )
        
        data = identity.to_dict()
        assert len(data["observations"]) == 2
        assert data["tone"] == "casual"
        assert data["confidence"] == 0.85
        
        # Deserialize
        restored = Identity.from_dict(data)
        assert len(restored.observations) == 2
        assert restored.tone == "casual"
        assert restored.confidence == 0.85


class TestIdentityStore:
    """Tests for IdentityStore persistence."""
    
    def test_store_creation_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            assert store.identity.observations == []
            assert not store.identity.is_usable()
    
    def test_add_observation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            store.add_observation("Uses casual language", 0.8)
            store.add_observation("Expresses appreciation", 0.9)
            
            assert len(store.identity.observations) == 2
            assert store.identity.observations[0].observation == "Uses casual language"
    
    def test_needs_digest_early_session(self):
        """Digest after 3 observations in first 5 turns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            # Not enough observations
            store.add_observation("Obs 1", 0.8)
            store.add_observation("Obs 2", 0.8)
            assert not store.needs_digest(current_turn_count=3)
            
            # Third observation triggers digest in early session
            store.add_observation("Obs 3", 0.8)
            assert store.needs_digest(current_turn_count=4)
    
    def test_needs_digest_normal_cadence(self):
        """Digest every 10 turns normally."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            # Add some observations
            for i in range(5):
                store.add_observation(f"Obs {i}", 0.8)
            
            # Simulate first digest at turn 5
            store.identity.turn_count_at_digest = 5
            store.identity.last_digest = datetime.now()
            # Reset the recent counter (digest resets it)
            store._recent_observation_count = 0
            
            # Not enough turns since last digest (only 5 turns passed)
            assert not store.needs_digest(current_turn_count=10)
            
            # After 10 turns since last digest (turn 15)
            assert store.needs_digest(current_turn_count=15)
    
    def test_pause_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            store.add_observation("Test", 0.8)
            assert len(store.identity.observations) == 1
            
            # Pause - should not add observations
            store.pause()
            store.add_observation("Ignored", 0.8)
            assert len(store.identity.observations) == 1  # Still 1
            
            # Resume
            store.resume()
            store.add_observation("New", 0.8)
            assert len(store.identity.observations) == 2
    
    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            store.add_observation("Test", 0.8)
            store.update_digest("Test prompt", 0.8, 5)
            
            assert store.identity.is_usable()
            
            store.clear()
            assert not store.identity.is_usable()
            assert len(store.identity.observations) == 0
    
    def test_persistence(self):
        """Test that identity persists to disk and can be reloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            
            # Create and populate store
            store1 = IdentityStore(session_path)
            store1.add_observation("Casual language", 0.8)
            store1.update_digest("User prefers casual.", 0.85, 5)
            
            # Create new store instance (should load from disk)
            store2 = IdentityStore(session_path)
            assert len(store2.identity.observations) == 1
            assert store2.identity.prompt == "User prefers casual."
            assert store2.identity.confidence == 0.85


class TestBehaviorExtraction:
    """Tests for behavior extraction patterns."""
    
    def test_extract_casual_language(self):
        behaviors = extract_behaviors_regex("lol that's funny haha")
        behavior_texts = [b[0] for b in behaviors]
        assert "Uses casual language" in behavior_texts
    
    def test_extract_appreciation(self):
        behaviors = extract_behaviors_regex("Thanks! That's really helpful.")
        behavior_texts = [b[0] for b in behaviors]
        assert "Expresses appreciation" in behavior_texts
    
    def test_extract_testing_memory(self):
        behaviors = extract_behaviors_regex("Do you remember my cat's name?")
        behavior_texts = [b[0] for b in behaviors]
        assert "Tests memory recall" in behavior_texts
    
    def test_extract_brevity(self):
        behaviors = extract_behaviors_regex("ok")
        behavior_texts = [b[0] for b in behaviors]
        assert "Prefers brief responses" in behavior_texts
    
    def test_no_behaviors(self):
        """Technical question shouldn't trigger behavioral patterns."""
        behaviors = extract_behaviors_regex("How do I configure the API timeout?")
        assert len(behaviors) == 0
    
    def test_prompt_format(self):
        """Verify extraction prompt contains expected structure."""
        assert "FACT:" in _TWO_TIER_EXTRACTION_PROMPT
        assert "BEHAVIOR:" in _TWO_TIER_EXTRACTION_PROMPT
        assert "NONE" in _TWO_TIER_EXTRACTION_PROMPT


class TestDigest:
    """Tests for identity digest functionality."""
    
    def test_extract_confidence(self):
        content = "User prefers casual interaction.\nCONFIDENCE: 0.85"
        confidence = _extract_confidence(content)
        assert confidence == 0.85
    
    def test_extract_confidence_missing(self):
        content = "User prefers casual interaction."
        confidence = _extract_confidence(content)
        assert confidence == 0.7  # Default
    
    def test_extract_prompt(self):
        content = "User prefers casual interaction.\nCONFIDENCE: 0.85"
        prompt = _extract_prompt(content)
        assert prompt == "User prefers casual interaction."
        assert "CONFIDENCE" not in prompt
    
    @pytest.mark.asyncio
    async def test_quick_digest_casual(self):
        observations = [
            "Uses casual language",
            "Uses informal tone",
            "Says lol frequently",
        ]
        prompt, confidence = await quick_digest(observations)
        assert prompt is not None
        assert "casual" in prompt.lower()
        assert confidence >= 0.5
    
    @pytest.mark.asyncio
    async def test_quick_digest_insufficient(self):
        observations = ["Single observation"]
        prompt, confidence = await quick_digest(observations)
        assert confidence == 0.5  # Not enough data


class TestInjection:
    """Tests for system prompt injection."""
    
    def test_injection_with_identity(self):
        identity = Identity(
            prompt="User prefers casual interaction.",
            confidence=0.85,
        )
        
        system_prompt = build_system_prompt_with_identity(
            "You are a helpful assistant.",
            identity,
            lens=self._make_lens_with_identity(),
        )
        
        assert "You are a helpful assistant." in system_prompt
        assert "User Interaction Style" in system_prompt
        assert "User prefers casual interaction." in system_prompt
        # Lens identity should be present
        assert "M'uru" in system_prompt
        assert "Your Identity" in system_prompt
    
    def _make_lens_with_identity(self):
        """Create a lens with M'uru identity for testing."""
        from sunwell.foundation.core.lens import Lens, LensMetadata
        from sunwell.core.models.heuristic import CommunicationStyle, Identity as LensIdentity
        
        return Lens(
            metadata=LensMetadata(name="test"),
            communication=CommunicationStyle(
                identity=LensIdentity(
                    name="M'uru",
                    nature="A test Naaru",
                )
            ),
        )
    
    def test_injection_without_identity(self):
        """RFC-131: No lens = no agent identity (clean design)."""
        system_prompt = build_system_prompt_with_identity(
            "You are a helpful assistant.",
            None,
        )
        
        # RFC-131: Without lens, no identity is injected
        assert "You are a helpful assistant." in system_prompt
        assert "Your Identity" not in system_prompt
        assert "User Interaction Style" not in system_prompt
    
    def test_injection_with_lens_identity(self):
        """RFC-131: Lens with identity gets injected."""
        system_prompt = build_system_prompt_with_identity(
            "You are a helpful assistant.",
            None,
            lens=self._make_lens_with_identity(),
        )
        
        assert "You are a helpful assistant." in system_prompt
        assert "M'uru" in system_prompt
        assert "Your Identity" in system_prompt
    
    def test_injection_disabled(self):
        """Can disable agent identity injection entirely."""
        system_prompt = build_system_prompt_with_identity(
            "You are a helpful assistant.",
            None,
            lens=self._make_lens_with_identity(),
            include_agent_identity=False,
        )
        
        assert system_prompt == "You are a helpful assistant."
        assert "M'uru" not in system_prompt
    
    def test_injection_low_confidence(self):
        """Low confidence user identity should not be injected."""
        identity = Identity(
            prompt="User prefers something.",
            confidence=0.5,  # Below threshold
        )
        
        system_prompt = build_system_prompt_with_identity(
            "You are a helpful assistant.",
            identity,
            lens=self._make_lens_with_identity(),
        )
        
        assert "User Interaction Style" not in system_prompt
        # Lens identity should still be present
        assert "M'uru" in system_prompt
    
    def test_injection_truncation(self):
        """Long identity prompts should be truncated."""
        identity = Identity(
            prompt="A" * 1000,  # Very long
            confidence=0.85,
        )
        
        system_prompt = build_system_prompt_with_identity(
            "Base prompt.",
            identity,
            max_identity_chars=100,
        )
        
        # Identity section should be present but truncated
        assert "User Interaction Style" in system_prompt
        # Original was 1000 chars, should be truncated to ~100
        identity_section = system_prompt.split("User Interaction Style")[1]
        assert len(identity_section) <= 150  # Some overhead for newlines


class TestIntegration:
    """Integration tests for the identity system."""
    
    def test_full_workflow(self):
        """Test complete workflow: observe → digest → inject."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            # 1. Add observations
            store.add_observation("Uses casual language like lol", 0.9)
            store.add_observation("Expresses appreciation frequently", 0.85)
            store.add_observation("Prefers informal tone", 0.8)
            
            # 2. Simulate digest (normally async with LLM)
            store.update_digest(
                prompt="This user prefers casual, friendly conversation.",
                confidence=0.88,
                turn_count=10,
                tone="casual and warm",
                values=["being remembered", "genuine interaction"],
            )
            
            # 3. Verify identity is usable
            assert store.identity.is_usable()
            assert store.identity.tone == "casual and warm"
            
            # 4. Inject into system prompt
            system_prompt = build_system_prompt_with_identity(
                "You are a helpful assistant.",
                store.identity,
            )
            
            assert "casual, friendly conversation" in system_prompt
    
    def test_export(self):
        """Test identity export functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions" / "test_session"
            store = IdentityStore(session_path)
            
            store.add_observation("Test observation", 0.8)
            store.update_digest("Test prompt", 0.85, 5)
            
            export = store.export()
            
            assert "identity" in export
            assert "observation_count" in export
            assert export["observation_count"] == 1
            assert export["is_usable"] == True
