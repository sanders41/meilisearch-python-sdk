import json

from httpx2 import Response


class BatchNotFoundError(Exception):
    pass


class InvalidDocumentError(Exception):
    """Error for documents that are not in a valid format for Meilisearch."""

    pass


class InvalidRestriction(Exception):
    pass


class MeilisearchError(Exception):
    """Generic class for Meilisearch error handling."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"MeilisearchError. Error message: {self.message}."


class MeilisearchApiError(MeilisearchError):
    """Error sent by Meilisearch API."""

    def __init__(self, error: str, response: Response) -> None:
        self.status_code = response.status_code
        self.code = ""
        self.message = ""
        self.link = ""
        self.error_type = ""
        error_json = None
        if response.content:
            try:
                error_json = response.json()
            except json.JSONDecodeError:
                error_json = None
        if isinstance(error_json, dict):
            self.message = f"Error message: {error_json.get('message') or ''}"
            self.code = f"{error_json.get('code') or ''}"
            self.error_type = f"{error_json.get('type') or ''}"
            self.link = f"Error documentation: {error_json.get('link') or ''}"
        else:
            self.message = error
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"MeilisearchApiError.{self.code} {self.message} {self.error_type} {self.link}"


class MeilisearchCommunicationError(MeilisearchError):
    """Error when connecting to Meilisearch."""

    def __str__(self) -> str:
        return f"MeilisearchCommunicationError, {self.message}"


class MeilisearchTaskFailedError(MeilisearchError):
    """Error when a task is in the failed status."""

    def __str__(self) -> str:
        return f"MeilisearchTaskFailedError, {self.message}"


class MeilisearchTimeoutError(MeilisearchError):
    """Error when Meilisearch operation takes longer than expected."""

    def __str__(self) -> str:
        return f"MeilisearchTimeoutError, {self.message}"


class PayloadTooLarge(Exception):
    """Error when the payload is larger than the allowed payload size."""

    pass


class InvalidTokenError(Exception):
    """Base exception when ``decode()`` fails on a token"""

    pass


class DecodeError(InvalidTokenError):
    """Raised when a token cannot be decoded because it failed validation"""

    pass


class InvalidIssuedAtError(InvalidTokenError):
    """Raised when a token's ``iat`` claim is non-numeric"""

    pass


class InvalidSignatureError(DecodeError):
    """Raised when a token's signature doesn't match the one provided as part of the token."""

    pass


class ImmatureSignatureError(InvalidTokenError):
    """Raised when a token's ``nbf`` or ``iat`` claims represent a time in the future"""

    pass


class ExpiredSignatureError(InvalidTokenError):
    """Raised when a token's ``exp`` claim indicates it has expired"""

    pass


class InvalidSubjectError(InvalidTokenError):
    """Raised when a token's ``sub`` claim is not a string"""

    pass


class InvalidJTIError(InvalidTokenError):
    """Raised when a token's ``jti`` claim is not a string"""

    pass
