import qbsdk
import os
import time
import pprint

pp = pprint.PrettyPrinter(indent=4)

api_key = os.environ['QB_API_KEY']
brand_address_private_key = os.environ['BRAND_ADDRESS_PRIVATE_KEY']
token_symbol = os.environ['BRAND_TOKEN_SYMBOL']
api = qbsdk.Api(api_key, brand_address_private_key, token_symbol)

transfer_receiver = '0x87265a62c60247f862b9149423061b36b460f4bb'

wallet = qbsdk.Wallet(brand_address_private_key, token_symbol, api, transfer_strategy=qbsdk.TransferStrategy.brand)

wallet.setup()

transfer_receiver = '0x87265a62c60247f862b9149423061b36b460f4bb'

start_millis = int(round(time.time() * 1000))
tx = wallet.send_transaction(transfer_receiver, 10)
print(f'Dispatched transaction with hash {tx.hash}. Polling for its completion..')

while True:
    try:
        processed_tx = api.get_transaction(tx.hash)
        pp.pprint(processed_tx)
        if processed_tx.confirms >= 1:
            break
        time.sleep(0.1)
    except qbsdk.error.NotFoundError as e:
        print(e)

end_millis = int(round(time.time() * 1000))
time_diff = end_millis - start_millis
print(f'Transaction end-to-end duration {time_diff}')
print(f'Transaction with hash {processed_tx.hash} was successfully confirmed.')

