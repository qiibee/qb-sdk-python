import backoff
import web3
from web3 import Web3
from eth_keys import keys
import eth_keys
from eth_utils import decode_hex
import logging
import qbsdk.loyalty_token as loyalty_token
import qbsdk.error as errors
from qbsdk.api import Token
from qbsdk.api import Transaction
from qbsdk.api import Api
from qbsdk.api import TokenType
from qbsdk.api import TransactionType
from typing import Callable
from enum import Enum
import eth_account

log = logging.getLogger(__name__)


class TransferStrategy(Enum):
    """
     Defines how the Wallet sends transactions. If the brand strategy is used, transaction nonces are
     fetched using an authenticated endpoint that allows faster transaction sending.
     If the user strategy is used, an endpoint giving the Ethereum address transactionCount is used.
    """
    brand = 'brand'
    user = 'user'

class BrandRetryConfig:

    def __init__(self, policy, jitter, interval, max_tries):
        self.policy =  policy
        self.jitter =jitter
        self.interval = interval
        self.max_tries = max_tries


DEFAULT_BRAND_RETRY_CONFIG = BrandRetryConfig(backoff.constant, backoff.full_jitter, 2, 10)


class TxData:
    def __init__(self, amount: int, address: str):
        self.amount = amount
        self.address = address

class Wallet:
    private_key: str
    checksum_address: str
    token_symbol: str
    token: Token
    api: Api
    __loyalty_contract: web3.contract.Contract
    _chain_id: int
    _transfer_strategy: TransferStrategy
    brand_retry_config: BrandRetryConfig = DEFAULT_BRAND_RETRY_CONFIG
    def __init__(self,
                 private_key: str,
                 token_symbol: str,
                 api: Api,
                 transfer_strategy: TransferStrategy = TransferStrategy.user):
        """
        :param str private_key: Ethereum address private key
        :param str token_symbol: Token symbol
        :param Api api: instance of API class to connect to the blockchain.
        :param TransferStrategy transfer_strategy: Can either be `brand` or `user`. Defaults to `user`.
        """
        self.private_key = private_key
        self._transfer_strategy = transfer_strategy
        self.token_symbol = token_symbol
        self.api = api
        self.token: Token = None
        self._chain_id: int = None
        self.web3_connection: Web3 = None
        self.__loyalty_contract = None

        if api is not None and api.api_key is None and transfer_strategy == TransferStrategy.brand:
            raise errors.ConfigError('API instance requires an api_key if employing a brand TransferStrategy')

        try:
            priv_key_bytes = decode_hex(private_key)
            priv_key = keys.PrivateKey(priv_key_bytes)
            pub_key = priv_key.public_key
            self.brand_address_public_key = pub_key
            self.checksum_address = self.brand_address_public_key.to_checksum_address()
        except eth_keys.exceptions.ValidationError as e:
            raise errors.ConfigError(f'Invalid brand private key: {str(e)}')

    @classmethod
    def create_random(cls,
                      token_symbol: str,
                      api: Api,
                      transfer_strategy: TransferStrategy = TransferStrategy.user):
        """
        Create a random new wallet, using what randomness your OS can provide
        :param str token_symbol:
        :param Api api:
        :param TransferStrategy transfer_strategy:
        :return:
        """

        new_eth_account = eth_account.Account.create()
        return cls(new_eth_account.key.hex(), token_symbol, api, transfer_strategy)


    def setup(self, token: Token = None, chain_id: str = None):
        """
        Call this method before making calls to send_transaction to enable sending. if token and chain_id are
        specified no I/O is done. If they are not, they are fetched from the API.
        :param Token token: nullable. If not defined it is fetched from the API based on symbol.
        :param str chain_id: nullable. If not defined it is fetched from API.
        :return: None
        """
        if self.api is None:
            raise errors.ConfigError('Api is not defined. Cannot make requests to the blockchain.')

        log.info(f'Wallet configured to use token {self.token_symbol}')

        if token is None:
            log.debug(f'Token uninitialized for {self.checksum_address}. fetching..')
            token = self.__get_token(self.token_symbol)
            if token is None:
                raise errors.ConfigError(f'Token with symbol {self.token_symbol} does not exist.')
        self.token = token

        log.info('Requesting blockchain network info..')

        if chain_id is None:
            log.debug(f'Chain id uninitialized for {self.checksum_address}. fetching..')
            last_block = self.api.get_last_block()
            chain_id = last_block.chain_id
        self._chain_id = chain_id

        logging.info(f'Setting up web3 contract with contract address {token.contract_address}')

        self.web3_connection = Web3()
        checksummed_contract_address = Web3.toChecksumAddress(token.contract_address)

        if token.token_type == TokenType.wallet:
            self.__loyalty_contract = self.web3_connection.eth.contract(
                abi=loyalty_token.abi,
                address=checksummed_contract_address)
        elif token.token_type == TokenType.nowallet:
            self.__loyalty_contract = self.web3_connection.eth.contract(
                abi=loyalty_token.no_wallet_abi,
                address=checksummed_contract_address)
        else:
            raise errors.ConfigError(f'Unsupported token type: {token.token_type}')



    def __get_token(self, symbol: str) -> Token:
        tokens = self.api.get_tokens(wallet_address=self.checksum_address)
        matches = list(filter(lambda token: token.symbol == symbol, tokens.private))
        if len(matches) == 0:
            return None
        else:
            return matches[0]

    def send_transaction(self, to: str, value: int, nonce=None, tx_type: TransactionType=None) -> Transaction:
        """
            Send a loyalty contract transfer to a particular 'to' address from the configured wallet address.
        :param to: Blockchain address of the receiver
        :param value: transfer value in wei
        :return: :class:`Transaction <Transaction>` object
        """
        if self.__loyalty_contract is None or self.web3_connection is None:
            raise errors.ConfigError('Call .setup() method first in order to be able to use this method.')

        if nonce is not None:
            return self.__send_transaction(to, value, nonce)

        if self._transfer_strategy is TransferStrategy.user:
            checksummed_contract_address = Web3.toChecksumAddress(self.token.contract_address)
            raw_tx = self.api.get_raw_transaction(self.checksum_address, to, value,
                                                  checksummed_contract_address, tx_type)
            raw_tx['gas'] = raw_tx['gasLimit']
            del raw_tx['gasLimit']
            return self.__send_web3_transaction(raw_tx)
        elif self._transfer_strategy is TransferStrategy.brand:

            if self.token.token_type == TokenType.wallet:
                def send(nonce: int):
                   self. __send_transaction(to, value, nonce)
                return self.__send_retryable_transaction(send)
            else:
                def send(nonce: int):
                   self.__send_nowallet_transaction(to, value, tx_type, nonce)
                return self.__send_retryable_transaction(send)

        else:
            raise ValueError('Unsupported transfer strategy.')


    @backoff.on_exception(backoff.constant,
                          errors.ConflictError,
                          jitter=backoff.full_jitter,
                          interval=2,
                          max_tries=10)
    def __send_retryable_transaction(self, send: Callable[[int], None]) -> Transaction:
        nonce = self.api._get_address_next_nonce(self.checksum_address)
        send(nonce)


    def __send_transaction(self, to: str, value: int, nonce) -> Transaction:
        log.info(f'Executing transaction to: {to}, value: {value} nonce: {nonce} on chain with id ${self._chain_id}')

        checksummed_to_address = Web3.toChecksumAddress(to)
        tx = self.__loyalty_contract.functions.transfer(checksummed_to_address, value).buildTransaction({
            'nonce': nonce,
            'gasPrice': 0,
            'gas': 1000000,
            'value': 0,
            'chainId': self._chain_id
        })
        return self.__send_web3_transaction(tx)

    def __send_nowallet_transaction(self, to: str, value: int, tx_type: TransactionType, nonce) -> Transaction:
        log.info(f'Executing transaction to: {to}, value: {value} nonce: {nonce} on chain with id ${self._chain_id}')

        tx_params = {
                'nonce': nonce,
                'gasPrice': 0,
                'gas': 1000000,
                'value': 0,
                'chainId': self._chain_id
            }

        if tx_type == TransactionType.reward:
            tx = self.__loyalty_contract.functions.earn(to, value).buildTransaction(tx_params)
        elif tx_type == TransactionType.debit:
            tx = self.__loyalty_contract.functions.debit(to, value).buildTransaction(tx_params)
        elif tx_type == TransactionType.redeem:
            tx = self.__loyalty_contract.functions.redeem(to, value).buildTransaction(tx_params)

        return self.__send_web3_transaction(tx)


    def __send_web3_transaction(self, raw_tx: dict) -> Transaction:
        signed_tx = self.web3_connection.eth.account.signTransaction(raw_tx, self.private_key)
        signed_tx_hex_string = signed_tx.rawTransaction.hex()

        return self.api.post_transaction(signed_tx_hex_string)


    def send_reward_batch(self, tx_data_list: [TxData]):
        if self.token != TokenType.nowallet:
            raise errors.UnsupportedOperationError(f'The token type does not support sending batches.')

        to_array = tx_data_list.map(lambda tx_data: tx_data.address)
        amount_array = tx_data_list.map(lambda tx_data: tx_data.amount)

        def send(nonce):
            tx = self.__loyalty_contract.functions.earnBatch(to_array, amount_array).buildTransaction({
                'nonce': nonce,
                'gasPrice': 0,
                'gas': 1000000,
                'value': 0,
                'chainId': self._chain_id
            })

            return self.__send_web3_transaction(tx)
        return self.__send_retryable_transaction(send)





