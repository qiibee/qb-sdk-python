import logging

from enum import Enum
import requests
from typing import Iterator, List, Dict
import qbsdk.error as errors

log = logging.getLogger(__name__)

class Mode(Enum):
    sandbox = 'sandbox'
    live = 'live'


API_HOSTS = {
    Mode.sandbox: 'https://api-sandbox.qiibee.com',
    Mode.live: 'https://api.qiibee.com'
}

API_VERSION = '0.0.1'

class Token(object):
    def __init__(self, json_object):
        self.contract_address: str = json_object['contractAddress']
        self.decimals: int = json_object['decimals']
        self.description: str = json_object['description']
        self.name: str = json_object['name']
        self.rate: int = json_object['rate']
        self.symbol: str = json_object['symbol']
        self.total_supply: int = json_object['totalSupply']


class Tokens(object):
    def __init__(self, private, public):
        self.public: List[Token] = public
        self.private: List[Token] = private


class TransactionState(Enum):
    processed = 'processed'
    pending = 'pending'


class Transaction(object):
    def __init__(self, json_object):

        self.block_hash: str = json_object['blockHash'] if 'blockHash' in json_object else None
        self.block_number: int = json_object['blockNumber'] if 'blockNumber' in json_object else None
        self.chain_id: int = json_object['chainId'] if 'chainId' in json_object else None
        self.from_address: str = json_object['from']
        self.hash: str = json_object['hash']
        self.input: str = json_object['input'] if 'input' in json_object else None
        self.nonce: int = json_object['nonce']
        self.to_address: str = json_object['to']
        self.transaction_index: int = json_object['transactionIndex'] if 'transactionIndex' in json_object else None
        self.value: int = int(json_object['value'])
        self.status: bool = json_object['status'] if 'status' in json_object else None
        self.contract: str = json_object['contract'] if 'contract' in json_object else json_object['contractAddress']
        self.timestamp: int = json_object['timestamp'] if 'timestamp' in json_object else None
        self.confirms: int = json_object['confirms'] if 'confirms' in json_object else None
        self.token: Token = Token(json_object['token']) if 'token' in json_object else None
        self.state: TransactionState = TransactionState(json_object['state'])


class Balance:
    balance: int
    def __init__(self, json_object):
        self.balance: int = int(json_object['balance'])
        self.contract_address: str = json_object['contractAddress']

class Address:
    def __init__(self, json_object):
        self.transaction_count: int = json_object['transactionCount']

        self.private_balances: Dict[str, Balance] = {}
        for symbol, json_balance in json_object['balances']['private'].items():
            self.private_balances[symbol] = Balance(json_balance)

        self.public_balances: Dict[str, Balance] = None
        if 'public' in json_object['balances']:
            self.public_balances = {}
            for symbol, json_balance in json_object['balances']['public'].items():
                self.public_balances[symbol] = Balance(json_balance)

class Block:
    def __init__(self, json_object):
        self.author: str = json_object['author']
        self.extra_data: str = json_object['extraData']
        self.hash: str = json_object['hash']
        self.miner: str = json_object['miner']
        self.number: int = json_object['number']
        self.parent_hash: int = json_object['parentHash']
        self.seal_fields: int = json_object['receiptsRoot']
        self.receipts_root: int = json_object['receiptsRoot']
        self.seal_fields: List[str] = json_object['sealFields']
        self.sha3_uncles: List[str] = json_object['sha3Uncles']
        self.signature: str = json_object['signature']
        self.size: int = json_object['size']
        self.state_root: str = json_object['stateRoot']
        self.step: str = json_object['step']
        self.timestamp: str = json_object['timestamp']
        self.transactions: List[str] = json_object['transactions']
        self.transactions_root: str = json_object['transactionsRoot']
        self.chain_id: str = json_object['chainId']

class TimestampedPrice:
    def __init__(self, json_object):
        self.time: int = json_object['time']
        self.price: float = json_object['price']

def do_request(api_base_url: str, method: str, path: str, params=None, data=None, api_key=None):
    headers = {
        'ApiVersion': API_VERSION
    }

    if api_key is not None:
        headers['Authorization'] = f'Bearer {api_key}'
    response = requests.request(method, f'{api_base_url}{path}', params=params, data=data, headers=headers)
    json_body = response.json()
    if response.status_code == 400:
        raise errors.InvalidRequestError(json_body['message'], 400)
    if response.status_code == 404:
        raise errors.NotFoundError(json_body['message'], 404)
    if response.status_code == 403:
        raise errors.AuthorizationError(json_body['message'], 403)
    if response.status_code == 409:
        raise errors.ConflictError(json_body['message'], 409)

    # if none of the above error codes match generically raise exception for the status
    response.raise_for_status()
    return json_body


class Api(object):
    api_key: str
    mode: Mode
    api_host: str
    def __init__(self, api_key: str, mode : Mode =Mode.sandbox):
        """The :class:`Api` object, represents a connection to the qiibee API which facilitates
         executing reads and transactions on the qiibee blockchain.

        :param str api_key: The brand API key (secret)
        :param str brand_address_private_key: The loyalty token source brand address private key
        :param int token_symbol: the symbol of the brand's token
        """
        self.api_key = api_key
        self.mode = mode
        self.api_host = API_HOSTS[self.mode]


    def get_token(self, contract_address: str) -> Token:
        """Returns a specific Loyalty Token on the qiibee chain.
        :param contract_address: Contract Address of the token
        :return: :class:`Token` object
        """

        json_body = do_request(self.api_host, 'GET', f'/tokens/{contract_address}')
        return Token(json_body['private'])


    def get_tokens(self, include_public_tokens: bool =False, wallet_address = None) -> Tokens:
        """
         Retrieve a list of tokens currently present on the loyalty blockchain, and potentially the relevant tokens
         on the ethereum main-net.
        :param include_public_tokens: includes the relevant tokens on the ethereum main-net. Defaults to False.
        :return: :class:`Tokens <Tokens>` object
        """
        query_params = {}

        if wallet_address is not None:
            query_params['walletAddress'] = wallet_address

        if include_public_tokens:
            query_params['public'] = 'true'

        json_body = do_request(self.api_host, 'GET', '/tokens', params=query_params)
        private = list(map(lambda json_token: Token(json_token), json_body['private']))
        public = list(map(lambda json_token: Token(json_token), json_body['public'])) if include_public_tokens else []
        return Tokens(private, public)


    def get_transaction(self, tx_hash: str) -> Transaction:
        """
        Retrieve details for a particular transaction loyalty blockchain transaction.
        :param tx_hash: the blockchain transaction hash.
        :return: :class:`Transaction <Transaction>` object
        """
        json_body = do_request(self.api_host, 'GET', f'/transactions/{tx_hash}')
        return Transaction(json_body)


    def get_raw_transaction(self, from_address: str, to_address: str, value: int, contract_address: str):
        json_body = do_request(self.api_host, 'GET', f'/transactions/raw', params={
            'from': from_address,
            'to': to_address,
            'transferAmount': value,
            'contractAddress': contract_address
        })

        return json_body

    def get_transactions(self, wallet: str = None,
                         limit: int = 100, offset: int = 0,
                         symbol: str = None, contract_address=None) -> Iterator[Transaction]:
        """
        Retrieve a paged list of transactions ordered descending by their blockchain timestamp.
        :param wallet: (optional) specify a 'wallet' filter to return only transactions to or from that wallet address.
        :param limit: (optional) specify a limit a to how many transactions to include in the response (defaults to 100).
        :param offset: (optional) specify an offset for the page of transactions to be returned (defaults to 0).
        :param symbol: specify a token symbol to only return transactions belonging to a particular token. (either specify symbol or contract address)
        :param contract_address: specify a contract address to only return transactions belonging to a particular token  with that contract address.
        :return: Iterator[Transaction]
        """

        query_params = {
            'offset': offset,
            'limit': limit
        }
        if wallet is not None:
            query_params['wallet'] = wallet
        if symbol is not None:
            query_params['symbol'] = symbol
        if contract_address is not None:
            query_params['contractAddress'] = contract_address


        json_body = do_request(self.api_host, 'GET', f'/transactions', params=query_params)
        return map(lambda json_tx: Transaction(json_tx), json_body)


    def get_address(self, address: str) -> Address:
        """
        Retrieve all the token balances and transaction counts for a particular address on the blockchain.
        :param address:
        :return: :class:`Address <Address>` object
        """
        json_body = do_request(self.api_host, 'GET', f'/addresses/{address}')
        return Address(json_body)


    def post_transaction(self, signed_tx_hex_string: str) -> Transaction:

        json_body = do_request(self.api_host, 'POST', f'/transactions/', data={
            'data': signed_tx_hex_string
        })

        json_body.pop('status', None)
        return Transaction(json_body)


    def get_last_block(self) -> Block:
        """
        Retrieve details of the last block in the chain.
        :return: :class:`Block <Block>` object
        """
        json_body = do_request(self.api_host, 'GET', f'/net')
        return Block(json_body)


    def _get_address_next_nonce(self, brand_address: str) -> int:
        json_body = do_request(self.api_host,
                               'GET', f'/addresses/{brand_address}/nextnonce',
                               api_key=self.api_key)

        return int(json_body['result'], 16)


    def get_prices(self, from_token_contract_address: str, to_currency_symbols: List[str] = None) -> Dict[str, str]:
        """
        Returns the FIAT price of one unit of a given Loyalty Token.
        This endpoint uses a third-party provider to get the ETH exchange rate.
        The QBX/ETH Exchange rate is fetched from the Coinsuper exchange.
        :return: :class:`Block <Block>` object
        """

        query_params = {
            'from': from_token_contract_address
        }

        if to_currency_symbols is not None and len(to_currency_symbols) > 0:
            currency_symbols_joined = ','.join(to_currency_symbols)
            query_params['to'] = currency_symbols_joined
        json_body = do_request(self.api_host, 'GET', f'/prices', params=query_params)
        return json_body


    def get_prices_history(self, from_token_contract_address: str, currency_symbol: str, limit: int = None) -> Iterator[TimestampedPrice]:
        """
        Returns the historical FIAT price values of one unit of a given Loyalty Token for a desired currency.
        This endpoint uses a third-party provider to get the ETH exchange rate.
        The QBX/ETH Exchange rate is fetched from the Coinsuper exchange.
        :return:
        """

        query_params = {
            'from': from_token_contract_address
        }

        if currency_symbol is not None:
            query_params['to']= currency_symbol
        if limit is not None:
            query_params['limit'] = limit


        json_body = do_request(self.api_host, 'GET', f'/prices/history', params=query_params)
        return map(lambda json_tx: TimestampedPrice(json_tx), json_body)
