from httpx import Response


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
        if response.content:
            self.message = f"Error message: {response.json().get('message') or ''}"
            self.code = f"{response.json().get('code') or ''}"
            self.error_type = f"{response.json().get('type') or ''}"
            self.link = f"Error documentation: {response.json().get('link') or ''}"
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
