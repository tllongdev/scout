"""Bundled OSINT tool specs. Importing this package registers them all."""

from __future__ import annotations

from ..registry import register
from . import (
    account_tools,
    crypto_tools,
    darkweb_tools,
    domain_tools,
    email_tools,
    geo_tools,
    http_tools,
    instagram_tools,
    news_tools,
    phone_tools,
    recon_tools,
    reddit_tools,
    sanctions_tools,
    scraping_tools,
    scrub_tools,
    spiderfoot_tools,
    surface_tools,
    telegram_tools,
    username_tools,
    vuln_tools,
)

for _module in (
    http_tools,
    reddit_tools,
    telegram_tools,
    scraping_tools,
    geo_tools,
    account_tools,
    username_tools,
    email_tools,
    phone_tools,
    domain_tools,
    instagram_tools,
    surface_tools,
    recon_tools,
    spiderfoot_tools,
    darkweb_tools,
    sanctions_tools,
    crypto_tools,
    vuln_tools,
    news_tools,
    scrub_tools,
):
    register(_module.SPECS)
