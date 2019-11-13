import logging

import web3
from web3 import Web3
from eth_keys import keys
import eth_keys
from eth_utils import decode_hex
from enum import Enum
import requests
from typing import Iterator, List, Dict
import threading
import time
import qbsdk.error as errors
import qbsdk.loyalty_token as loyalty_token


log = logging.getLogger(__name__)

class Mode(Enum):
    sandbox = 'sandbox'
    live = 'live'


API_HOSTS = {
    Mode.sandbox: "https://apitesting.qiibee.com",
    Mode.live: "https://api.qiibee.com"
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


def do_request(api_base_url: str, method: str, path: str, data=None, api_key=None):
    headers = {
        'ApiVersion': API_VERSION
    }

    if api_key is not None:
        headers['Authorization'] = f'Bearer {api_key}'
    response = requests.request(method, f'{api_base_url}{path}', data=data, headers=headers)
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
    brand_address_private_key: str
    brand_address_public_key: str
    brand_checksum_address: str
    token_symbol: str
    mode: Mode
    api_host: str
    brand_token: Token
    loyalty_contract: web3.contract.Contract
    def __init__(self, api_key: str, brand_address_private_key: str, token_symbol: str, mode : Mode =Mode.sandbox):
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
            self.brand_checksum_address = self.brand_address_public_key.to_checksum_address()
        except eth_keys.exceptions.ValidationError as e:
            raise errors.ConfigError(f'Invalid brand private key: {str(e)}')

        # these are intialized during setup (I/O required)
        self.brand_token: Token = None
        self.chain_id: int = None
        self.web3_connection: Web3 = None
        self.loyalty_contract = None


    def setup(self):
        """
        Call this method before making calls to send_transaction to enable sending.
        :return: None
        """
        log.info(f'Api connection configured to use token {self.token_symbol}')
        token = self.__get_token(self.token_symbol)
        if token is None:
            raise errors.ConfigError(f'Token with symbol {self.token_symbol} does not exist.')
        self.brand_token = token

        log.info('Requesting blockchain network info..')

        last_block = self.get_last_block()
        self.chain_id = last_block.chain_id

        logging.info(f'Setting up web3 contract with contract address {token.contract_address}')

        self.web3_connection = Web3()
        checksummed_contract_address = Web3.toChecksumAddress(token.contract_address)
        self.loyalty_contract = self.web3_connection.eth.contract(abi=loyalty_token.abi, address=checksummed_contract_address)


    def get_tokens(self, include_public_tokens: bool =False) -> Tokens:
        """
         Retrieve a list of tokens currently present on the loyalty blockchain, and potentially the relevant tokens
         on the ethereum main-net.
        :param include_public_tokens: includes the relevant tokens on the ethereum main-net. Defaults to False.
        :return: :class:`Tokens <Tokens>` object
        """
        query_params = f'?walletAddress={self.brand_checksum_address}'
        if include_public_tokens:
            query_params += '&public=true'

        json_body = do_request(self.api_host, 'GET', f'/tokens{query_params}')
        private = list(map(lambda json_token: Token(json_token), json_body['private']))
        public = list(map(lambda json_token: Token(json_token), json_body['public'])) if include_public_tokens else []
        return Tokens(private, public)


    def __get_token(self, symbol: str) -> Token:
        tokens = self.get_tokens()
        matches = list(filter(lambda token: token.symbol == symbol, tokens.private))
        if len(matches) == 0:
            return None
        else:
            return matches[0]


    def get_transaction(self, tx_hash: str) -> Transaction:
        """
        Retrieve details for a particular transaction loyalty blockchain transaction.
        :param tx_hash: the blockchain transaction hash.
        :return: :class:`Transaction <Transaction>` object
        """
        json_body = do_request(self.api_host, 'GET', f'/transactions/{tx_hash}')
        return Transaction(json_body)


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
        query_params = f'?offset={offset}&limit={limit}'
        if wallet is not None:
            query_params += f'&wallet={wallet}'
        if symbol is not None:
            query_params += f'&symbol={symbol}'
        if contract_address is not None:
            query_params += f'&contractAddress={contract_address}'


        json_body = do_request(self.api_host, 'GET', f'/transactions{query_params}')
        return map(lambda json_tx: Transaction(json_tx), json_body)


    def get_address(self, address: str) -> Address:
        """
        Retrieve all the token balances and transaction counts for a particular address on the blockchain.
        :param address:
        :return: :class:`Address <Address>` object
        """
        json_body = do_request(self.api_host, 'GET', f'/addresses/{address}')
        return Address(json_body)

    def send_transaction(self, to: str, value: int, nonce=None) -> Transaction:
        """
            Send a loyalty contract transfer to a particular 'to' address from the configured brand address.
        :param to: Blockchain address of the receiver
        :param value: transfer value in wei
        :return: :class:`Transaction <Transaction>` object
        """
        if self.loyalty_contract is None or self.web3_connection is None:
            raise errors.ConfigError('Call .setup() method first in order to be able to use this method.')

        if nonce is None:
            nonce = self.increment_and_get_nonce()
        log.info(f'Executing transaction to: {to}, value: {value} nonce: {nonce} on chain with id ${self.chain_id}')

        checksummed_to_address = Web3.toChecksumAddress(to)
        tx = self.loyalty_contract.functions.transfer(checksummed_to_address, value).buildTransaction({
            'nonce': nonce,
            'gasPrice': 0,
            'gas': 1000000,
            'value': 0,
            'chainId': self.chain_id
        })

        signed_tx = self.web3_connection.eth.account.signTransaction(tx, self.brand_address_private_key)

        signed_tx_hex_string = signed_tx.rawTransaction.hex()

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

    def overwrite_nonce_with_current_transaction_count(self) -> int:
        brand_address = self.get_address(self.brand_address_public_key)
        log.info(f'Overwriting current nonce with transaction count value {brand_address.transaction_count}')
        return self.__put_nonce(brand_address.transaction_count)

    def get_nonce(self) -> int:
        """
        Get next nonce to be used for the specified brand addressed as stored by the API (not necessarily in sync
        with the blockchain transactionCount).
        :return: nonce int
        """

        json_body = do_request(self.api_host, 'GET',
                               f'/addresses/{self.brand_checksum_address}/nonce',
                               api_key=self.api_key)
        return json_body['nonce']

    def put_nonce(self, nonce: int) -> int:
        json_body = do_request(self.api_host, 'PUT',
                               f'/addresses/{self.brand_checksum_address}/nonce', data={
            'nonce': nonce
        }, api_key=self.api_key)

        return json_body['nonce']

    def increment_and_get_nonce(self):
        json_body = do_request(self.api_host, 'PATCH',
                               f'/addresses/{self.brand_checksum_address}/nonce',
                               api_key=self.api_key)
        return json_body['nonce']

    def _sync_tx_count_to_nonce(self):
        brand_address = self.get_address(self.brand_checksum_address)
        log.info(f'Brand address {self.brand_checksum_address} has transactionCount={brand_address.transaction_count}')
        log.info(f'Synching to nonce..')
        self.put_nonce(brand_address.transaction_count)


    def run_skipped_nonce_recovery(self):
        """
        This is an error-state recovery function. In case your python process error while sending transfers
        it may be the case that the nonce was incremented but the TX was not sent, which will result in transactions
        nonces being skipped. If that is the case run this method while making sure no other transactions are currently
        happening to revert
        :return:
        """
        (transaction_count, current_nonce) = self.__get_tx_count_and_nonce()
        if current_nonce < transaction_count:
            log.warning(f'Current stored nonce is behind the transactionCount. Setting it to match transactionCount')
            self.put_nonce(transaction_count)
        elif current_nonce == transaction_count:
            log.info(f'Brand address transactionCount and stored nonce are in synch. Nothing to do.')
        else:
            nonce_diff = current_nonce - transaction_count
            log.warning(f'Current stored nonce is ahead of the transactionCount.'
                        f' Highly probably nonces have been skipped. Generating {nonce_diff} no-ops to get them in synch..')
            self.__run_no_ops_for_skipped_nonces(transaction_count, current_nonce)


    __NO_OP_BATCH_SIZE = 25
    __NO_OP_TRANSFER_RECEIVER = '0x66384f39Bd9Cb1Eb9393a8f4a97e0E8Eb2Bb3766'
    __NO_OP_TRANSFER_AMOUNT = 0

    def __run_no_ops_for_skipped_nonces(self, transaction_count: int, current_nonce: int):
        nonce_diff = current_nonce - transaction_count
        log.info(f'Difference between current nonce and transactionCount is {nonce_diff}')
        log.info(f'Executing no-op transactions in batches of max {self.__NO_OP_BATCH_SIZE} to cover the gaps.')
        batch_index = 0
        nonce_to_use = transaction_count
        while nonce_diff > 0:
            batch_size = min([self.__NO_OP_BATCH_SIZE, nonce_diff])
            log.info(f'Executing batch {batch_index} of size {batch_size}')
            threads = []
            for i in range(0, batch_size):
                thread = threading.Thread(target=self.__send_no_op_transaction, args=(nonce_to_use,))
                thread.start()
                threads.append(thread)
                nonce_to_use +=1

            # wait for all to finish..
            log.info(f'Waiting for all batch no-ops to finish..')
            for thread in threads:
                thread.join()

            batch_index += 1
            batch_sleep_time = 5
            log.info(f'Sleeping for {batch_sleep_time} before doing a new batch.')
            time.sleep(batch_sleep_time)
            (transaction_count, current_nonce) = self.__get_tx_count_and_nonce()
            nonce_diff = current_nonce - transaction_count
            log.info(f'Difference between current nonce and transactionCount is {nonce_diff}')
            nonce_to_use = transaction_count


    def __send_no_op_transaction(self, nonce: int):
        log.debug(f'Sending no-op tx tx with nonce {nonce}')
        tx: Transaction
        try:
            tx = self.send_transaction(self.__NO_OP_TRANSFER_RECEIVER, self.__NO_OP_TRANSFER_AMOUNT, nonce)
        except errors.ConflictError as e:
            log.debug(f'No-op tx collided with existing transaction with the same nonce. Moving on.')
            return
        except Exception as e:
            raise e

        print(f'Pending for finishing of no-op tx with hash {tx.hash} and nonce {nonce}')
        start_millis = int(round(time.time() * 1000))
        while True:
            try:
                processed_tx = self.get_transaction(tx.hash)
                if processed_tx.confirms >= 1:
                    break
                time.sleep(0.1)
            except errors.NotFoundError as e:
                log.debug(f'No-op tx with hash {tx.hash} still not available.')
            except Exception as e:
                raise e
            end_millis = int(round(time.time() * 1000))
            if end_millis - start_millis > 10000:
                log.info(f'Skipping check for tx {tx.hash}. Mostly likely was superseeded by an existing tx pool tx.')
                break

    def __get_tx_count_and_nonce(self) -> (int, int):
        brand_address = self.get_address(self.brand_checksum_address)
        log.info(
            f'Brand address {self.brand_checksum_address} has transactionCount={brand_address.transaction_count}')

        current_nonce = self.get_nonce()
        log.info(
            f'Brand address {self.brand_checksum_address} has stored nonce={current_nonce}')
        return (brand_address.transaction_count, current_nonce)

