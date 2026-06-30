"""Data-hygiene tools ('scrub'), in both senses of the word:

1. redact_pii   - strip personal data out of collected text (Microsoft Presidio)
2. data_broker_optout - surface opt-out / removal links for people-search brokers
"""

from __future__ import annotations

import json
from typing import Any

from ...llm import Tool
from ..registry import BuildContext, ToolSpec

# Static, maintained-by-hand map of major people-search/data-broker opt-outs.
_BROKERS: dict[str, str] = {
    "Spokeo": "https://www.spokeo.com/optout",
    "Whitepages": "https://www.whitepages.com/suppression-requests",
    "BeenVerified": "https://www.beenverified.com/app/optout/search",
    "Intelius": "https://www.intelius.com/opt-out/",
    "PeopleFinders": "https://www.peoplefinders.com/opt-out",
    "Radaris": "https://radaris.com/control/privacy",
    "MyLife": "https://www.mylife.com/ccpa/index.pubview",
    "TruePeopleSearch": "https://www.truepeoplesearch.com/removal",
    "FastPeopleSearch": "https://www.fastpeoplesearch.com/removal",
    "InstantCheckmate": "https://www.instantcheckmate.com/opt-out/",
    "TruthFinder": "https://www.truthfinder.com/opt-out/",
    "PeopleConnect": "https://www.peopleconnect.us/optout",
    "Acxiom": "https://isapps.acxiom.com/optout/optout.aspx",
    "LexisNexis": "https://optout.lexisnexis.com/",
    "Epsilon": "https://www.epsilon.com/us/consumer-information/privacy-faqs",
}


def _redact(ctx: BuildContext) -> list[Tool]:
    def _handle(args: dict[str, Any]) -> str:
        text = str(args.get("text", ""))
        if not text.strip():
            return "Error: 'text' is required."
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            analyzer = AnalyzerEngine()
            results = analyzer.analyze(text=text, language="en")
            anonymized = AnonymizerEngine().anonymize(text=text, analyzer_results=results)
            return anonymized.text
        except Exception as exc:  # noqa: BLE001
            return f"PII redaction failed: {exc}"

    return [
        Tool(
            name="redact_pii",
            description=(
                "Redact personally identifiable information (names, emails, phones, "
                "SSNs, credit cards, locations, etc.) from a block of text using "
                "Microsoft Presidio. Use before sharing or exporting sensitive notes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to scrub."}
                },
                "required": ["text"],
            },
            handler=_handle,
        )
    ]


def _broker_optout(ctx: BuildContext) -> list[Tool]:
    def _handle(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        listing = [{"broker": b, "optout_url": u} for b, u in _BROKERS.items()]
        return json.dumps(
            {"subject": name or "(unspecified)", "brokers": listing}, indent=2
        )

    return [
        Tool(
            name="data_broker_optout",
            description=(
                "List the opt-out / removal pages for major people-search data "
                "brokers (Spokeo, Whitepages, BeenVerified, Radaris, LexisNexis, "
                "etc.) so a person can be scrubbed from the internet. Returns the "
                "broker names and their opt-out URLs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Optional: the person these requests are for.",
                    }
                },
            },
            handler=_handle,
        )
    ]


SPECS = [
    ToolSpec(
        id="redact_pii",
        name="Presidio (scrub)",
        category="data hygiene",
        summary="Redact PII/secrets from collected text.",
        builder=_redact,
        import_check="presidio_analyzer",
        install_hint="pip install presidio-analyzer presidio-anonymizer && "
        "python -m spacy download en_core_web_lg",
        docs="https://github.com/microsoft/presidio",
        keywords=("redact", "scrub", "anonymize", "sanitize", "pii",
                  "remove personal", "mask sensitive"),
    ),
    ToolSpec(
        id="broker_optout",
        name="Data-broker opt-out",
        category="data hygiene",
        summary="Opt-out/removal links for people-search data brokers.",
        builder=_broker_optout,
        keyless=True,
        docs="https://github.com/yaph/data-broker-opt-out",
    ),
]
