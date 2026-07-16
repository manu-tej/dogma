"""Tests for conversation tagging and search functionality."""

import pytest
from uuid import uuid4

from quration.utils.tag_validator import (
    validate_tag,
    validate_tags,
    merge_tags,
    TagValidationError,
)


class TestTagValidation:
    """Test tag validation utilities."""

    def test_validate_tag_success(self):
        """Test valid tags are normalized correctly."""
        assert validate_tag("RNA-Seq") == "rna-seq"
        assert validate_tag("experiment123") == "experiment123"
        assert validate_tag("  Melanoma  ") == "melanoma"
        assert validate_tag("covid-19") == "covid-19"

    def test_validate_tag_empty(self):
        """Test empty tags are rejected."""
        with pytest.raises(TagValidationError, match="must be a non-empty string"):
            validate_tag("")

        with pytest.raises(TagValidationError, match="must be a non-empty string"):
            validate_tag(None)

    def test_validate_tag_too_long(self):
        """Test tags exceeding max length are rejected."""
        long_tag = "a" * 51
        with pytest.raises(TagValidationError, match="exceeds maximum length"):
            validate_tag(long_tag)

    def test_validate_tag_invalid_characters(self):
        """Test tags with invalid characters are rejected."""
        invalid_tags = [
            "tag with spaces",
            "tag_underscore",
            "tag@special",
            "tag.dot",
            "-leading-hyphen",
            "trailing-hyphen-",
        ]
        for tag in invalid_tags:
            with pytest.raises(TagValidationError, match="must contain only"):
                validate_tag(tag)

    def test_validate_tags_list(self):
        """Test validating multiple tags."""
        tags = ["RNA-Seq", "Melanoma", "Experiment"]
        result = validate_tags(tags)
        assert result == ["rna-seq", "melanoma", "experiment"]

    def test_validate_tags_removes_duplicates(self):
        """Test duplicate tags are removed."""
        tags = ["RNA-Seq", "rna-seq", "MELANOMA", "melanoma"]
        result = validate_tags(tags)
        assert result == ["rna-seq", "melanoma"]

    def test_validate_tags_max_limit(self):
        """Test maximum tag limit is enforced."""
        tags = [f"tag{i}" for i in range(21)]
        with pytest.raises(TagValidationError, match="Cannot add more than"):
            validate_tags(tags)

    def test_merge_tags_success(self):
        """Test merging new tags with existing."""
        existing = ["rna-seq", "melanoma"]
        new = ["experiment", "covid-19"]
        result = merge_tags(existing, new)
        assert set(result) == {"rna-seq", "melanoma", "experiment", "covid-19"}

    def test_merge_tags_deduplicates(self):
        """Test merge removes duplicates."""
        existing = ["rna-seq", "melanoma"]
        new = ["RNA-Seq", "experiment"]
        result = merge_tags(existing, new)
        assert set(result) == {"rna-seq", "melanoma", "experiment"}

    def test_merge_tags_enforces_max(self):
        """Test merge enforces maximum total tags."""
        existing = [f"tag{i}" for i in range(45)]
        new = [f"newtag{i}" for i in range(10)]
        with pytest.raises(TagValidationError, match="would exceed maximum"):
            merge_tags(existing, new)


class TestConversationTagsIntegration:
    """Integration tests for conversation tags (requires database).

    These tests should be run with a test database configured.
    Mark with @pytest.mark.integration if you have that marker set up.
    """

    @pytest.mark.skip(reason="Requires database setup")
    async def test_add_tags_to_conversation(self):
        """Test adding tags to a conversation."""
        # This would require:
        # 1. Test database session
        # 2. Create test conversation
        # 3. Add tags
        # 4. Verify tags are stored
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_remove_tag_from_conversation(self):
        """Test removing a tag from a conversation."""
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_search_conversations_by_tags(self):
        """Test searching conversations by tags."""
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_search_conversations_by_text(self):
        """Test searching conversations by text query."""
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_search_conversations_combined(self):
        """Test searching with both tags and text query."""
        pass


class TestConversationTagsAPI:
    """API endpoint tests for conversation tags.

    These tests should use FastAPI TestClient.
    Mark with @pytest.mark.api if you have that marker set up.
    """

    @pytest.mark.skip(reason="Requires API test client setup")
    def test_post_conversation_tags_endpoint(self):
        """Test POST /api/v1/conversations/{id}/tags endpoint."""
        # This would test:
        # 1. Valid tag addition
        # 2. Invalid tags rejected
        # 3. Authorization checks
        # 4. 404 for non-existent conversation
        pass

    @pytest.mark.skip(reason="Requires API test client setup")
    def test_delete_conversation_tag_endpoint(self):
        """Test DELETE /api/v1/conversations/{id}/tags/{tag} endpoint."""
        # This would test:
        # 1. Tag removal
        # 2. Case-insensitive removal
        # 3. Idempotency (removing non-existent tag)
        # 4. Authorization checks
        pass

    @pytest.mark.skip(reason="Requires API test client setup")
    def test_search_conversations_endpoint(self):
        """Test GET /api/v1/conversations/search endpoint."""
        # This would test:
        # 1. Search by text only
        # 2. Search by tags only
        # 3. Combined search
        # 4. Pagination
        # 5. Relevance scoring
        # 6. Empty results
        pass


# Manual test scenarios for verification

def print_manual_test_scenarios():
    """Print manual test scenarios for verification.

    These should be run manually against a running API instance.
    """
    scenarios = """
    MANUAL TEST SCENARIOS FOR CONVERSATION TAGGING
    ==============================================

    Setup:
    1. Start the API server with database migration applied
    2. Create a test user and get auth token
    3. Create 3-4 test conversations with messages

    Test 1: Add Tags to Conversation
    ---------------------------------
    POST /api/v1/conversations/{id}/tags
    Body: {"tags": ["rna-seq", "melanoma", "experiment"]}

    Expected: 200 OK with conversation showing new tags

    Test 2: Add Invalid Tags
    ------------------------
    POST /api/v1/conversations/{id}/tags
    Body: {"tags": ["invalid tag", "tag_with_underscore"]}

    Expected: 400 Bad Request with validation error

    Test 3: Remove Tag
    ------------------
    DELETE /api/v1/conversations/{id}/tags/melanoma

    Expected: 200 OK with conversation missing that tag

    Test 4: Remove Non-Existent Tag (Idempotent)
    --------------------------------------------
    DELETE /api/v1/conversations/{id}/tags/nonexistent

    Expected: 200 OK with conversation unchanged

    Test 5: Search by Tags Only
    ---------------------------
    GET /api/v1/conversations/search?tags=rna-seq,melanoma

    Expected: 200 OK with conversations having ALL specified tags

    Test 6: Search by Text Only
    ---------------------------
    GET /api/v1/conversations/search?q=cancer

    Expected: 200 OK with conversations containing "cancer" in title or messages

    Test 7: Combined Search
    ----------------------
    GET /api/v1/conversations/search?q=melanoma&tags=rna-seq

    Expected: 200 OK with conversations matching both criteria, sorted by relevance

    Test 8: Search with Pagination
    ------------------------------
    GET /api/v1/conversations/search?q=experiment&limit=2&offset=0
    GET /api/v1/conversations/search?q=experiment&limit=2&offset=2

    Expected: Paginated results

    Test 9: Verify Tags in List Conversations
    -----------------------------------------
    GET /api/v1/conversations

    Expected: All conversations include tags field

    Test 10: Authorization Check
    ----------------------------
    Try to add tags to another user's conversation

    Expected: 403 Forbidden
    """
    print(scenarios)


if __name__ == "__main__":
    print_manual_test_scenarios()
