"""
Shared type aliases for the NewsLens platform.
"""

from __future__ import annotations

from typing import TypeAlias
from uuid import UUID

PublisherName: TypeAlias = str
ArticleId: TypeAlias = str
ChunkId: TypeAlias = str
SessionId: TypeAlias = UUID
BiasScore: TypeAlias = float
