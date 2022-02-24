from httpx import Response


class InvalidDocumentError(Exception):
    """Error for documents that are not in a valid format for MeiliSearch."""

    pass


class InvalidRestriction(Exception):
    pass


class MeiliSearchError(Exception):
    """Generic class for MeiliSearch error handling."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"MeiliSearchError. Error message: {self.message}."


class MeiliSearchApiError(MeiliSearchError):
    """Error sent by MeiliSearch API."""

    def __init__(self, error: str, response: Response) -> None:
        self.status_code = response.status_code
        self.code = ""
        self.message = ""
        self.link = ""
        self.error_type = ""
        if response.content:
            self.message = f" Error message: {response.json().get('message') or ''}."
            self.code = f"{response.json().get('code') or ''}"
            self.error_type = f"{response.json().get('type') or ''}"
            self.link = f" Error documentation: {response.json().get('link') or ''}"
        else:
            self.message = error
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"MeiliSearchApiError.{self.code}{self.message}{self.error_type}{self.link}"


class MeiliSearchCommunicationError(MeiliSearchError):
    """Error when connecting to MeiliSearch."""

    def __str__(self) -> str:
        return f"MeiliSearchCommunicationError, {self.message}"


class MeiliSearchTimeoutError(MeiliSearchError):
    """Error when MeiliSearch operation takes longer than expected."""

    def __str__(self) -> str:
        return f"MeiliSearchTimeoutError, {self.message}"


class PayloadTooLarge(Exception):
    """Error when the payload is larger than the allowed payload size."""

    pass
