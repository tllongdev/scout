"""Bundled OSINT tool specs. Importing this package registers them all."""

from __future__ import annotations

from ..registry import register
from . import (
    account_tools,
    darkweb_tools,
    geo_tools,
    http_tools,
    recon_tools,
    reddit_tools,
    scraping_tools,
    scrub_tools,
)

for _module in (
    http_tools,
    reddit_tools,
    scraping_tools,
    geo_tools,
    account_tools,
    recon_tools,
    darkweb_tools,
    scrub_tools,
):
    register(_module.SPECS)
