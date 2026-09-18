"""Tests for PromptPayloadBuilder constructing clean, token-efficient, secret-free prompts."""

from __future__ import annotations

import json
import pytest

from autoslide.planner.builder import PromptPayloadBuilder
from tests.fixtures.planner_samples import create_sample_deck_inventory


def test_build_prompt_payload():
    inventory = create_sample_deck_inventory()
    builder = PromptPayloadBuilder()

    instruction = "Update slide 1 title to 'Q4 Financial Review' and make subtitle italic."
    payload = builder.build_payload(
        user_instruction=instruction,
        inventory=inventory,
    )

    assert "system_prompt" in payload
    assert "user_prompt" in payload
    assert "schema" in payload

    # Verify user instruction included
    assert "Q4 Financial Review" in payload["user_prompt"]

    # Verify inventory and stable fingerprints included
    assert "Executive Summary" in payload["user_prompt"]
    assert inventory.slides[0].shapes[0].fingerprint in payload["user_prompt"]

    # Verify no credentials, API keys, or machine secrets
    user_p = payload["user_prompt"].lower()
    assert "api_key" not in user_p
    assert "sk-" not in user_p
    assert "/home/" not in user_p
    assert "/media/" not in user_p


def test_build_prompt_compact_inventory():
    inventory = create_sample_deck_inventory()
    builder = PromptPayloadBuilder()

    compact_manifest = builder.format_compact_inventory(inventory)
    assert isinstance(compact_manifest, str)
    assert "Slide 1" in compact_manifest
    assert "Slide 2" in compact_manifest
    assert "Financial Table" in compact_manifest
