import msgpack
from eth_utils import keccak, to_hex
from eth_account.messages import encode_structured_data
from eth_account.signers.local import LocalAccount

def address_to_bytes(address):
    return bytes.fromhex(address[2:] if address.startswith("0x") else address)

def construct_phantom_agent(hash, is_mainnet):
    return {"source": "a" if is_mainnet else "b", "connectionId": hash}

def action_hash(action, vault_address, nonce):
    data = msgpack.packb(action)
    data += nonce.to_bytes(8, "big")
    if vault_address is None:
        data += b"\x00"
    else:
        data += b"\x01"
        data += address_to_bytes(vault_address)
    return keccak(data)

def sign_inner(wallet: LocalAccount, data):
    structured_data = encode_structured_data(data)
    signed = wallet.sign_message(structured_data)
    return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

def sign_l1_action(wallet, action, active_pool, nonce, is_mainnet):
    hash = action_hash(action, active_pool, nonce)
    phantom_agent = construct_phantom_agent(hash, is_mainnet)
    data = {
        "domain": {
            "chainId": 1337,
            "name": "Exchange",
            "verifyingContract": "0x0000000000000000000000000000000000000000",
            "version": "1",
        },
        "types": {
            "Agent": [
                {"name": "source", "type": "string"},
                {"name": "connectionId", "type": "bytes32"},
            ],
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
        },
        "primaryType": "Agent",
        "message": phantom_agent,
    }
    return sign_inner(wallet, data)

