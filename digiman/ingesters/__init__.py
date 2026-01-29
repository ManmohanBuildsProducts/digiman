"""Data ingesters for Digiman."""

from .granola import GranolaIngester
from .slack import SlackIngester

__all__ = ["GranolaIngester", "SlackIngester"]
