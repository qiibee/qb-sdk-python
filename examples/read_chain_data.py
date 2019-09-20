import qbsdk
import os

print('Reading chain data..')

api_key = os.environ['QB_API_KEY']
brand_address_private_key = os.environ['BRAND_ADDRESS_PRIVATE_KEY']
token_symbol = os.environ['BRAND_TOKEN_SYMBOL']
api = qbsdk.Api(api_key, brand_address_private_key, token_symbol)

tokens = api.get_tokens()
for token in tokens.private:
    print(vars(token))

latest_transactions = list(api.get_transactions())
print(f'Retrieved the last {len(latest_transactions)}')

latest_transaction = latest_transactions[0]

latest_transaction = api.get_transaction(latest_transaction.hash)
print(f'Latest transaction {latest_transaction.hash} has {latest_transaction.confirms} confirmations.')

sending_address = api.get_address(latest_transaction.from_address)
print(f'Sending address {latest_transaction.from_address} has the following balances:')
for token_name, balance in sending_address.private_balances.items():
    print(f'{token_name}: {vars(balance)}')