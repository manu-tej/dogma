"""Tag validation utilities for conversation tagging."""

import re
from typing import List


class TagValidationError(Exception):
    """Raised when tag validation fails."""
    pass


def validate_tag(tag: str) -> str:
    """Validate and normalize a single tag.

    Tags must be:
    - Lowercase
    - Alphanumeric with hyphens allowed
    - Between 1 and 50 characters
    - Not only whitespace or special characters

    Args:
        tag: The tag to validate

    Returns:
        Normalized tag (lowercase, trimmed)

    Raises:
        TagValidationError: If tag is invalid
    """
    if not tag or not isinstance(tag, str):
        raise TagValidationError("Tag must be a non-empty string")

    # Normalize: lowercase and trim
    normalized = tag.lower().strip()

    # Check length
    if len(normalized) < 1:
        raise TagValidationError("Tag cannot be empty after normalization")
    if len(normalized) > 50:
        raise TagValidationError(f"Tag '{normalized}' exceeds maximum length of 50 characters")

    # Check format: alphanumeric and hyphens only
    if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', normalized):
        raise TagValidationError(
            f"Tag '{normalized}' must contain only lowercase letters, numbers, and hyphens. "
            "Cannot start or end with a hyphen."
        )

    return normalized


def validate_tags(tags: List[str], max_tags: int = 20) -> List[str]:
    """Validate and normalize a list of tags.

    Args:
        tags: List of tags to validate
        max_tags: Maximum number of tags allowed (default: 20)

    Returns:
        List of normalized, unique tags

    Raises:
        TagValidationError: If any tag is invalid or too many tags provided
    """
    if not isinstance(tags, list):
        raise TagValidationError("Tags must be provided as a list")

    if len(tags) > max_tags:
        raise TagValidationError(f"Cannot add more than {max_tags} tags at once")

    # Validate each tag and collect unique ones
    normalized_tags = []
    seen = set()

    for tag in tags:
        try:
            normalized = validate_tag(tag)
            if normalized not in seen:
                normalized_tags.append(normalized)
                seen.add(normalized)
        except TagValidationError as e:
            # Re-raise with context about which tag failed
            raise TagValidationError(f"Invalid tag '{tag}': {str(e)}")

    return normalized_tags


def merge_tags(existing_tags: List[str], new_tags: List[str], max_total: int = 50) -> List[str]:
    """Merge new tags with existing tags, avoiding duplicates.

    Args:
        existing_tags: Current tags on the conversation
        new_tags: New tags to add
        max_total: Maximum total tags allowed (default: 50)

    Returns:
        Merged list of unique tags

    Raises:
        TagValidationError: If merge would exceed max_total
    """
    # Normalize existing tags
    existing_set = set(tag.lower().strip() for tag in (existing_tags or []))

    # Validate and normalize new tags
    validated_new = validate_tags(new_tags)

    # Merge
    merged = list(existing_set)
    for tag in validated_new:
        if tag not in existing_set:
            merged.append(tag)

    # Check total limit
    if len(merged) > max_total:
        raise TagValidationError(
            f"Total tags ({len(merged)}) would exceed maximum of {max_total}. "
            f"Remove some existing tags first."
        )

    return merged
