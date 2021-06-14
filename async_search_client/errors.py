from httpx import Response


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
        self.error_code = ""
        self.message = ""
        self.error_link = ""
        if response.text:
            self.message = f" Error message: {response.json().get('message') or ''}."
            self.error_code = f"{response.json().get('errorCode') or ''}"
            self.error_link = f" Error documentation: {response.json().get('errorLink') or ''}"
        else:
            self.message = error
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"MeiliSearchApiError.{self.error_code}{self.message}{self.error_link}"


class MeiliSearchCommunicationError(MeiliSearchError):
    """Error when connecting to MeiliSearch."""

    def __str__(self) -> str:
        return f"MeiliSearchCommunicationError, {self.message}"


class MeiliSearchTimeoutError(MeiliSearchError):
    """Error when MeiliSearch operation takes longer than expected."""

    def __str__(self) -> str:
        return f"MeiliSearchTimeoutError, {self.message}"
