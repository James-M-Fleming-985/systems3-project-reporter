"""
Encryption Service — GDPR-compliant field-level encryption
Uses Fernet (AES-256-CBC) symmetric encryption for client names and financial data.
Key sourced from FGSI_ENCRYPTION_KEY environment variable.
"""
import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to use cryptography library; fall back to a no-op if unavailable
try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    InvalidToken = Exception
    logger.warning("cryptography package not installed — encryption disabled. "
                   "Run: pip install cryptography")


class EncryptionService:
    """Field-level encryption service for GDPR-sensitive data."""

    def __init__(self, key: Optional[str] = None):
        """
        Initialise with an encryption key.

        Args:
            key: Base64-encoded Fernet key.  If *None*, reads from
                 FGSI_ENCRYPTION_KEY env var.  If neither is set the
                 service operates in **passthrough mode** (no encryption).
        """
        self._fernet = None
        self._enabled = False

        raw_key = key or os.getenv("FGSI_ENCRYPTION_KEY")
        if not raw_key:
            logger.warning("FGSI_ENCRYPTION_KEY not set — encryption disabled (passthrough mode)")
            return

        if not HAS_CRYPTOGRAPHY:
            logger.warning("cryptography package missing — encryption disabled")
            return

        try:
            self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
            self._enabled = True
            logger.info("EncryptionService initialised — field-level encryption ACTIVE")
        except Exception as exc:
            logger.error(f"Invalid encryption key: {exc}")
            raise ValueError(
                "FGSI_ENCRYPTION_KEY is not a valid Fernet key. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string.  Returns base64-encoded ciphertext, or the
        original string if encryption is disabled."""
        if not self._enabled or not plaintext:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string.  Returns the original plaintext, or the
        input unchanged if encryption is disabled or input is not encrypted."""
        if not self._enabled or not ciphertext:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            # Value was stored in plaintext (pre-encryption migration)
            return ciphertext

    def encrypt_dict_fields(self, data: dict, fields: list[str]) -> dict:
        """Return a shallow copy of *data* with the named *fields* encrypted."""
        out = dict(data)
        for f in fields:
            if f in out and out[f] is not None:
                out[f] = self.encrypt(str(out[f]))
        return out

    def decrypt_dict_fields(self, data: dict, fields: list[str]) -> dict:
        """Return a shallow copy of *data* with the named *fields* decrypted."""
        out = dict(data)
        for f in fields:
            if f in out and out[f] is not None:
                out[f] = self.decrypt(str(out[f]))
        return out

    # ------------------------------------------------------------------
    # Key management helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (for initial setup / rotation)."""
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required — pip install cryptography")
        return Fernet.generate_key().decode("utf-8")
