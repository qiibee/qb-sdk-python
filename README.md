# qb-sdk-python
Brand SDK for the qiibee blockchain.


## Requirements

To use this library, use the qiibee dashboard account to retrieve the API key present at https://dashboard.qiibee.com/developers

## Installation

> pip install qb-sdk

## Example usage

Import the SDK library:

> import qbsdk

Initialize the API object:

```.python
api_key = os.environ['QB_API_KEY']
brand_address_private_key = os.environ['BRAND_ADDRESS_PRIVATE_KEY']
token_symbol = os.environ['BRAND_TOKEN_SYMBOL']
api = qbsdk.Api(api_key)
``` 

Fetch existing tokens:

```.python
tokens = api.get_tokens()
for token in tokens.private:
    print(vars(token))
```

Reward a particular user:

```.python

wallet = qbsdk.Wallet(brand_address_private_key, token_symbol, api, transfer_strategy=qbsdk.TransferStrategy.brand)

wallet.setup()

transfer_receiver = '0x87265a62c60247f862b9149423061b36b460f4bb'
tx = wallet.send_transaction(transfer_receiver, 10)
```

Check out the [examples](https://github.com/qiibee/qb-sdk-python/tree/master/examples) directory for more comprehensive examples.

