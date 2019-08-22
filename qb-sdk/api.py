import logging

log = logging.getLogger(__name__)

class Api(object):
    token_symbol: str
    def __init__(self):
        pass

    def setup(self, api_key: str, brand_address_private_key: str, token_symbol: str):
        self.token_symbol = token_symbol
        log.info(f'Api connection configured to use token {token_symbol}')