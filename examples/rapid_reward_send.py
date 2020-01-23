from gevent import monkey
monkey.patch_all()
import qbsdk
import time
import threading
import os

# This example uses gevent to optimize the I/O calls  performance

api_key = os.environ['QB_API_KEY']
brand_address_private_key = os.environ['BRAND_ADDRESS_PRIVATE_KEY']
token_symbol = os.environ['BRAND_TOKEN_SYMBOL']

api = qbsdk.Api(api_key)

wallet = qbsdk.Wallet(brand_address_private_key, token_symbol, api, qbsdk.TransferStrategy.brand)
wallet.setup()
transfer_receiver = '0x87265a62c60247f862b9149423061b36b460f4bb'

TOTAL_TX_COUNT = 10
POLLING_INTERVAL_MS = 200

def wait_for_tx_completion(tx):
    print(f'Checking for tx {tx.hash}')
    while True:
        try:
            processed_tx = api.get_transaction(tx.hash)
            if processed_tx.confirms >= 1:
                # consider tx completed.
                break
            sleep_time = POLLING_INTERVAL_MS / 1000
            time.sleep(sleep_time)
        except qbsdk.error.NotFoundError as e:
            # Tx has not been processed yet.
            sleep_time = POLLING_INTERVAL_MS / 1000
            print(f'Sleeping for {sleep_time}')
            time.sleep(sleep_time)
        except Exception as e:
            print(f'ERROR: {e}')
            # some other error occured. Retry your transaction.
    print(f'Transaction with hash {processed_tx.hash}')

# To send transactions at optimal throughput from one address
# send them sequentially as shown below.
# Check for transaction completion in an asynchronous fashion.
# The example here uses a Thread and gevent which when using gevent converts to
#  a Greenlet http://www.gevent.org/api/gevent.greenlet.html
# Using it without gevent works too, albeit somewhat slower.
for i in range(0, TOTAL_TX_COUNT):
    print(f'Sending tx {i}')
    i += 1
    start_millis =  int(round(time.time() * 1000))
    try:
        pending_tx = wallet.send_transaction(transfer_receiver, i)
    except Exception as e:
        print(f'Failed with {e}')
        continue
    thread = threading.Thread(target=wait_for_tx_completion, args=(pending_tx,))
    thread.start()
print('finished.')
