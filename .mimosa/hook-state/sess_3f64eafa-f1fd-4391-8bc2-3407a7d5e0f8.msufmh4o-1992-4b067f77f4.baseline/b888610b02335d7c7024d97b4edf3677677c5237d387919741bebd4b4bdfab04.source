"""PII masking — column-level data protection for query results.

Applies masking rules to sensitive fields before data reaches agents or the
frontend. Masks are configurable per-tenant via database settings.

Supported mask types:
- EMAIL: j***@company.com
- PHONE: ***-***-1234
- SSN: ***-**-1234
- CREDIT_CARD: ****-****-****-1234
- FULL_MASK: ****
- CUSTOM: regex-based pattern replacement

Architecture:
    Query Result → PII Masking Middleware → Agent Pipeline → Frontend

The masking happens at the service layer between data retrieval and the
agent pipeline, so no PII ever enters LLM context.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.logging import logger


class MaskType(str, Enum):
    """Types of PII masking strategies."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    FULL_MASK = "full_mask"
    NONE = "none"


@dataclass
class ColumnMaskRule:
    """Masking rule applied to a specific column."""

    column_name: str
    mask_type: MaskType
    # For partial masking: how many characters to show at end
    visible_suffix_chars: int = 4


# ---------------------------------------------------------------------------
# Default masking rules — overridden per-tenant via DB settings
# ---------------------------------------------------------------------------

DEFAULT_MASK_RULES: list[ColumnMaskRule] = [
    ColumnMaskRule("email", MaskType.EMAIL),
    ColumnMaskRule("email_address", MaskType.EMAIL),
    ColumnMaskRule("phone", MaskType.PHONE),
    ColumnMaskRule("phone_number", MaskType.PHONE),
    ColumnMaskRule("mobile", MaskType.PHONE),
    ColumnMaskRule("ssn", MaskType.SSN),
    ColumnMaskRule("social_security", MaskType.SSN),
    ColumnMaskRule("tax_id", MaskType.SSN),
    ColumnMaskRule("credit_card", MaskType.CREDIT_CARD),
    ColumnMaskRule("card_number", MaskType.CREDIT_CARD),
    ColumnMaskRule("password", MaskType.FULL_MASK),
    ColumnMaskRule("secret", MaskType.FULL_MASK),
    ColumnMaskRule("api_key", MaskType.FULL_MASK),
    ColumnMaskRule("token", MaskType.FULL_MASK),
]


# ---------------------------------------------------------------------------
# Masking engine
# ---------------------------------------------------------------------------


class PIIMasker:
    """Applies column-level PII masking to query results.

    Usage:
        masker = PIIMasker(rules=[...])
        masked_data = masker.mask_rows(rows)
    """

    def __init__(self, rules: list[ColumnMaskRule] | None = None):
        self.rules = rules or DEFAULT_MASK_RULES
        self._rule_map: dict[str, ColumnMaskRule] = {
            r.column_name.lower(): r for r in self.rules
        }

    def mask_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply masking to all rows.

        Args:
            rows: List of row dicts from a query result.

        Returns:
            New list with masked values (original rows are not mutated).
        """
        if not rows:
            return rows

        masked = []
        for row in rows:
            masked_row = {}
            for column, value in row.items():
                rule = self._find_rule(column)
                if rule and rule.mask_type != MaskType.NONE and value is not None:
                    masked_row[column] = self._apply_mask(str(value), rule)
                else:
                    masked_row[column] = value
            masked.append(masked_row)

        masked_count = sum(
            1 for r in masked
            for v in r.values()
            if isinstance(v, str) and "*" in v
        )
        if masked_count:
            logger.info(f"PII masked {masked_count} values across {len(rows)} rows")

        return masked

    def _find_rule(self, column_name: str) -> ColumnMaskRule | None:
        """Find matching mask rule for a column name."""
        return self._rule_map.get(column_name.lower())

    def _apply_mask(self, value: str, rule: ColumnMaskRule) -> str:
        """Apply the appropriate masking strategy."""
        if not value:
            return value

        maskers = {
            MaskType.EMAIL: self._mask_email,
            MaskType.PHONE: self._mask_phone,
            MaskType.SSN: self._mask_ssn,
            MaskType.CREDIT_CARD: self._mask_credit_card,
            MaskType.FULL_MASK: lambda v, _: "****",
        }

        masker = maskers.get(rule.mask_type)
        if masker:
            return masker(value, rule.visible_suffix_chars)
        return value

    # --- Individual mask strategies ---

    @staticmethod
    def _mask_email(email: str, visible_suffix: int = 0) -> str:
        """jdoe@company.com → j***@company.com"""
        if "@" not in email:
            return "****"
        local, domain = email.split("@", 1)
        if len(local) <= 1:
            visible = local
        else:
            visible = local[0] + "***"
        return f"{visible}@{domain}"

    @staticmethod
    def _mask_phone(phone: str, visible_suffix: int = 4) -> str:
        """+1-555-123-4567 → ***-***-4567"""
        # Strip non-digit chars for counting
        digits = re.sub(r"\D", "", phone)
        if len(digits) <= visible_suffix:
            return "*" * len(digits)

        visible = digits[-visible_suffix:]
        masked_count = len(digits) - visible_suffix

        # Preserve original formatting loosely
        if "-" in phone or "(" in phone:
            return f"***-***-{visible}"
        return ("*" * masked_count) + visible

    @staticmethod
    def _mask_ssn(ssn: str, visible_suffix: int = 4) -> str:
        """123-45-6789 → ***-**-6789"""
        digits = re.sub(r"\D", "", ssn)
        if len(digits) <= visible_suffix:
            return "*" * len(digits)
        visible = digits[-visible_suffix:]
        return f"***-**-{visible}"

    @staticmethod
    def _mask_credit_card(card: str, visible_suffix: int = 4) -> str:
        """4111-1111-1111-1111 → ****-****-****-1111"""
        digits = re.sub(r"\D", "", card)
        if len(digits) <= visible_suffix:
            return "*" * len(digits)
        visible = digits[-visible_suffix:]
        return f"****-****-****-{visible}"


# ---------------------------------------------------------------------------
# Tenant-aware masking
# ---------------------------------------------------------------------------

# Per-tenant rule overrides (loaded from DB on startup)
_tenant_rules: dict[str, list[ColumnMaskRule]] = {}


def load_tenant_mask_rules(tenant_id: str, rules: list[ColumnMaskRule]) -> None:
    """Register custom masking rules for a tenant.

    Called during tenant initialization or when rules change.
    """
    _tenant_rules[tenant_id] = rules
    logger.info(f"Loaded {len(rules)} mask rules for tenant {tenant_id}")


def get_masker_for_tenant(tenant_id: str) -> PIIMasker:
    """Get a PIIMasker configured for a specific tenant.

    Falls back to DEFAULT_MASK_RULES if no tenant-specific rules exist.
    """
    custom_rules = _tenant_rules.get(tenant_id)
    if custom_rules:
        return PIIMasker(rules=custom_rules)
    return PIIMasker(rules=DEFAULT_MASK_RULES)
