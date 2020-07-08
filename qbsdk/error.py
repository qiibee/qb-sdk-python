

class QiibeeError(Exception):
    def __init__(self, message, http_status_code=None):
        self.http_status_code = http_status_code
        self.message = message

class InvalidRequestError(QiibeeError):
    pass

class AuthorizationError(QiibeeError):
    pass

class ConfigError(QiibeeError):
    pass

class NotFoundError(QiibeeError):
    pass

class ConflictError(QiibeeError):
    pass

class ServerResponseParseError(QiibeeError):
    pass

class UnsupportedOperationError(QiibeeError):
    pass
