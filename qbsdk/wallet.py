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
from enum import Enum
import eth_account

log = logging.getLogger(__name__)


class TransferStrategy(Enum):
    brand = 'brand'
    user = 'user'

class BrandRetryConfig:

    def __init__(self, policy, jitter, interval, max_tries):
        self.policy =  policy
        self.jitter =jitter
        self.interval = interval
        self.max_tries = max_tries


DEFAULT_BRAND_RETRY_CONFIG = BrandRetryConfig(backoff.constant, backoff.full_jitter, 2, 10)

class Wallet:
    private_key: str
    checksum_address: str
    token_symbol: str
    brand_token: Token
    __loyalty_contract: web3.contract.Contract
    _chain_id: int
    _transfer_strategy: TransferStrategy
    brand_retry_config: BrandRetryConfig = DEFAULT_BRAND_RETRY_CONFIG
    def __init__(self,
                 private_key: str,
                 token_symbol: str,
                 api: Api,
                 transfer_strategy: TransferStrategy = TransferStrategy.user):
        self.private_key = private_key
        self._transfer_strategy = transfer_strategy
        self.token_symbol = token_symbol
        self.api = api
        self.brand_token: Token = None
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
            self.brand_checksum_address = self.brand_address_public_key.to_checksum_address()
        except eth_keys.exceptions.ValidationError as e:
            raise errors.ConfigError(f'Invalid brand private key: {str(e)}')

    @classmethod
    def create_random(cls,
                      token_symbol: str,
                      api: Api,
                      transfer_strategy: TransferStrategy = TransferStrategy.user):

        new_eth_account = eth_account.Account.create()
        return cls(new_eth_account.key.hex(), token_symbol, api, transfer_strategy)


    def setup(self):
        """
        Call this method before making calls to send_transaction to enable sending.
        :return: None
        """
        if self.api is None:
            raise errors.ConfigError('Api is not defined. Cannot make requests to the blockchain.')

        log.info(f'Wallet configured to use token {self.token_symbol}')
        token = self.__get_token(self.token_symbol)
        if token is None:
            raise errors.ConfigError(f'Token with symbol {self.token_symbol} does not exist.')
        self.brand_token = token

        log.info('Requesting blockchain network info..')

        last_block = self.api.get_last_block()
        self._chain_id = last_block.chain_id

        logging.info(f'Setting up web3 contract with contract address {token.contract_address}')

        self.web3_connection = Web3()
        checksummed_contract_address = Web3.toChecksumAddress(token.contract_address)
        self.__loyalty_contract = self.web3_connection.eth.contract(abi=loyalty_token.abi, address=checksummed_contract_address)


    def __get_token(self, symbol: str) -> Token:
        tokens = self.api.get_tokens(wallet_address=self.brand_checksum_address)
        matches = list(filter(lambda token: token.symbol == symbol, tokens.private))
        if len(matches) == 0:
            return None
        else:
            return matches[0]

    def send_transaction(self, to: str, value: int, nonce=None) -> Transaction:
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
            raw_tx = self.api.get_raw_transaction(self.checksum_address, to, value, checksummed_contract_address)
        elif self._transfer_strategy is TransferStrategy.brand:
            return self.__send_retryable_transaction(to, value)
        else:
            raise ValueError('Unsupported transfer strategy.')


    @backoff.on_exception(backoff.constant,
                          errors.ConflictError,
                          jitter=backoff.full_jitter,
                          interval=2,
                          max_tries=10)
    def __send_retryable_transaction(self, to: str, value: int) -> Transaction:
        nonce = self.api._get_address_next_nonce(self.brand_checksum_address)
        return self.__send_transaction(to, value, nonce)


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

        signed_tx = self.web3_connection.eth.account.signTransaction(tx, self.private_key)

        signed_tx_hex_string = signed_tx.rawTransaction.hex()

        return self.api.post_transaction(signed_tx_hex_string)




