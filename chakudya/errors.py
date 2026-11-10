class ChakudyaApiError(Exception):
    """Raised for any non-2xx reply, an {"status": "error"} body, a timeout or a network failure.

    `status` is 0 for timeouts and network failures. `body` is the decoded JSON
    (or the raw text when the reply was not JSON).
    """

    def __init__(self, message, status=0, body=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.body = body

    def __str__(self):
        return f"ChakudyaApiError({self.status}): {self.message}"
