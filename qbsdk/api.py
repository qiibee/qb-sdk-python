import logging
from eth_keys import keys
import eth_keys
from eth_utils import decode_hex
from enum import Enum
import requests
from typing import Iterator
import qbsdk.error as errors


log = logging.getLogger(__name__)

class Mode(Enum):
    sandbox = 'sandbox'
    live = 'live'


API_HOSTS = {
    Mode.sandbox: "https://apitesting.qiibee.com",
    Mode.live: "https://api.qiibee.com"
}

class Token(object):
    def __init__(self, json_object):
        self.contract_address = json_object['contractAddress']
        self.decimals = json_object['decimals']
        self.description = json_object['description']
        self.name = json_object['name']
        self.rate = json_object['rate']
        self.symbol = json_object['symbol']
        self.total_supply = json_object['totalSupply']

class Tokens(object):
    def __init__(self, private, public):
        self.public = public
        self.private = private


class TransactionState(Enum):
    processed = 'processed'
    pending = 'pending'


class Transaction(object):
    def __init__(self, json_object):
        self.block_hash = json_object['blockHash']
        self.block_number = json_object['blockNumber']
        self.chain_id = json_object['chainId'] if 'chainId' in json_object else None
        self.from_address = json_object['from']
        self.hash = json_object['hash']
        self.input = json_object['input']
        self.nonce = json_object['nonce']
        self.to_address = json_object['to']
        self.transaction_index = json_object['transactionIndex']
        self.value = int(json_object['value'])
        self.status = json_object['status']
        self.contract = json_object['contract'] if 'contract' in json_object else json_object['contractAddress']
        self.timestamp = json_object['timestamp']
        self.confirms = json_object['confirms']
        self.token = Token(json_object['token'])
        self.state = TransactionState(json_object['state'])


class Balance:
    balance: int
    def __init__(self, json_object):
        self.balance = int(json_object['balance'])
        self.contract_address = json_object['contractAddress']

class Address:
    def __init__(self, json_object):
        self.transaction_count = json_object['transactionCount']

        self.private_balances = {}
        for symbol, json_balance in json_object['balances']['private'].items():
            self.private_balances[symbol] = Balance(json_balance)

        if 'public' in json_object['balances']:
            self.public_balances = {}
            for symbol, json_balance in json_object['balances']['public'].items():
                self.public_balances[symbol] = Balance(json_balance)


class Api(object):
    api_key: str
    brand_address_private_key: str
    token_symbol: str
    mode: Mode
    api_host: str
    brand_token: Token
    def __init__(self, api_key: str, brand_address_private_key: str, token_symbol: str, mode=Mode.sandbox):
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

        try:
            priv_key_bytes = decode_hex(brand_address_private_key)
            priv_key = keys.PrivateKey(priv_key_bytes)
            pub_key = priv_key.public_key
            self.brand_address_public_key = pub_key
        except eth_keys.exceptions.ValidationError as e:
            raise errors.ConfigError(str(e))


    def setup(self):
        log.info(f'Api connection configured to use token {self.token_symbol}')
        token = self.__get_token(self.token_symbol)
        if token is None:
            raise errors.ConfigError(f'Token with symbol {self.token_symbol} does not exist.')
        self.brand_token = token


    def get_tokens(self, include_public_tokens=False) -> Tokens:
        query_params = '?public=true' if include_public_tokens else ''
        response = requests.get(f'{self.api_host}/tokens{query_params}')
        json_body = response.json()
        private = list(map(lambda json_token: Token(json_token), json_body['private']))
        public = list(map(lambda json_token: Token(json_token), json_body['public'])) if include_public_tokens else []
        return Tokens(private, public)


    def __get_token(self, symbol) -> Token:
        tokens = self.get_tokens()
        matches = list(filter(lambda token: token.symbol == symbol, tokens.private))
        if len(matches) == 0:
            return None
        else:
            return matches[1]


    def get_transaction(self, tx_hash: str) -> Transaction:
        response = requests.get(f'{self.api_host}/transactions/{tx_hash}')
        json_body = response.json()
        return Transaction(json_body)


    def get_transactions(self, wallet: str = None,
                         limit: int = 100, offset: int = 0,
                         symbol: str = None, contract_address=None) -> Iterator[Transaction]:
        query_params = f'?offset={offset}&limit={limit}'
        if wallet is not None:
            query_params += f'&wallet={wallet}'
        if symbol is not None:
            query_params += f'&symbol={symbol}'
        if contract_address is not None:
            query_params += f'&contractAddress={contract_address}'

        response = requests.get(f'{self.api_host}/transactions{query_params}')
        json_body = response.json()
        return map(lambda json_tx: Transaction(json_tx), json_body)


    def get_address(self, address: str) -> Address:
        response = requests.get(f'{self.api_host}/addresses/{address}')
        json_body = response.json()
        return Address(json_body)