class ApiError(Exception):
    def __init__(self, http_status_code, message):
        self.http_status_code = http_status_code
        self.message = message

class ConfigError(Exception):
    pass