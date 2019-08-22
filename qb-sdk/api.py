import logging

log = logging.getLogger(__name__)

class Api(object):
    api_key: str
    brand_address_private_key: str
    token_symbol: str
    def __init__(self, api_key: str, brand_address_private_key: str, token_symbol: str):
        """The :class:`Api` object, represents a connection to the Qiibee API which facilitates
         executing reads and transactions on the Qiibee blockchain.


        :param str api_key: The brand API key (secret)
        :param str brand_address_private_key: The loyalty token source brand address private key
        :param int token_symbol: the symbol of the brand's token
        """
        self.api_key = api_key
        self.brand_address_private_key = brand_address_private_key
        self.token_symbol = token_symbol


    def setup(self):
        log.info(f'Api connection configured to use token {self.token_symbol}')