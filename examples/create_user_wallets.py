import qbsdk
import os

# Create a custodial wallet on the server-side
random_uninitialized_wallet = qbsdk.Wallet.create_random(None, None)

print(f'Created custodial user wallet with address {random_uninitialized_wallet.checksum_address}'
      f'Store its wallet.private_key safely. Without it, access to the funds is irreversibly lost.')

# You can access the private key at random_uninitialized_wallet.private_key .
# Ensure this is stored safely and ideally encrypted.


token_symbol = os.environ['BRAND_TOKEN_SYMBOL']
other_user_private_key = os.environ['USER_ADDRESS_PRIVATE_KEY']

api = qbsdk.Api(None)

# Create wallet from an existing private key with defined symbol and api to be able to send
other_user = qbsdk.Wallet(other_user_private_key, token_symbol, api, qbsdk.TransferStrategy.user)

# initialize in order to be able to transactions
other_user.setup()

# send 1000 wei tokens to the newly created user
other_user.send_transaction(random_uninitialized_wallet.checksum_address, 1000)
