import logging
from enum import Enum
import requests


class Mode(Enum):
    SANDBOX = 'sandbox'
    LIVE = 'live'


API_HOSTS = {
    Mode.SANDBOX: "https://apitesting.qiibee.com",
    Mode.LIVE: "https://api.qiibee.com"
}

log = logging.getLogger(__name__)

class Api(object):
    api_key: str
    brand_address_private_key: str
    token_symbol: str
    mode: Mode
    api_host: str
    def __init__(self, api_key: str, brand_address_private_key: str, token_symbol: str, mode=Mode.SANDBOX):
        """The :class:`Api` object, represents a connection to the qiibee API which facilitates
         executing reads and transactions on the qiibee blockchain.


        :param str api_key: The brand API key (secret)
        :param str brand_address_private_key: The loyalty token source brand address private key
        :param int token_symbol: the symbol of the brand's token
        """
        self.api_key = api_key
        self.brand_address_private_key = brand_address_private_key
        self.token_symbol = token_symbol
        self.mode = mode
        self.api_host = API_HOSTS[self.mode]


    def setup(self):
        log.info(f'Api connection configured to use token {self.token_symbol}')
        tokens_response = self.get_tokens()

    def get_tokens(self):
        response = requests.get(f'{self.api_host}/{symbol}')
