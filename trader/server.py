"""
MCP Server for FourMeme token trading on BSC.
Provides tools to query token data via Bitquery v2 API
and execute swaps via PancakeSwap V2 Router.
"""

import json
import os
import time

import aiohttp
from web3 import Web3

from mcp.server.fastmcp import FastMCP

# ── server ────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "fourmeme-trader",
    instructions="FourMeme token analytics on BSC via Bitquery and swap execution via PancakeSwap",
)

# ── Config ────────────────────────────────────────────────────────────────────

BITQUERY_URL = "https://streaming.bitquery.io/graphql"
BITQUERY_TOKEN = os.getenv("BITQUERY_TOKEN", "")

BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")

PANCAKE_ROUTER_V2 = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
FOURMEME_FACTORY = "0x5c952063c7fc8610ffdb798152d69f0b9550762b"

# ── Web3 setup ────────────────────────────────────────────────────────────────

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))

ROUTER_ABI = json.loads("""[
  {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactETHForTokensSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"payable","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"swapExactTokensForETHSupportingFeeOnTransferTokens","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],"stateMutability":"view","type":"function"}
]""")

ERC20_ABI = json.loads("""[
  {"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]""")

router = w3.eth.contract(address=PANCAKE_ROUTER_V2, abi=ROUTER_ABI)


def _get_wallet():
    if not WALLET_PRIVATE_KEY:
        return None, None
    account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
    return account, account.address


# ── Bitquery helper ───────────────────────────────────────────────────────────

async def _bitquery(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BITQUERY_TOKEN}",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(BITQUERY_URL, json=payload, headers=headers) as resp:
            data = await resp.json()
            if "errors" in data:
                return {"error": data["errors"]}
            return data.get("data", {})


# ── Data tools (Bitquery) ────────────────────────────────────────────────────

@mcp.tool()
async def get_fourmeme_tokens(limit: int = 20) -> list[dict]:
    """
    Get recently traded FourMeme tokens on BSC.
    Returns token name, symbol, address, trade count, buy/sell volume, and unique traders.
    """
    query = """
    query ($limit: Int) {
      EVM(network: bsc, dataset: combined) {
        DEXTradeByTokens(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Dex: {
                OwnerAddress: {is: "%s"}
              }
            }
          }
          orderBy: {descendingByField: "trades"}
          limit: {count: $limit}
        ) {
          Trade {
            Currency {
              Name
              Symbol
              SmartContract
            }
            Dex {
              ProtocolName
              SmartContract
            }
          }
          trades: count
          buyers: count(distinct: Trade_Buy_Buyer)
          sellers: count(distinct: Trade_Buy_Seller)
          buy_volume: sum(of: Trade_Buy_AmountInUSD)
          sell_volume: sum(of: Trade_Sell_AmountInUSD)
          last_trade: maximum(of: Block_Time)
        }
      }
    }
    """ % FOURMEME_FACTORY
    data = await _bitquery(query, {"limit": limit})
    rows = data.get("EVM", {}).get("DEXTradeByTokens", [])
    return [
        {
            "name": r["Trade"]["Currency"]["Name"],
            "symbol": r["Trade"]["Currency"]["Symbol"],
            "address": r["Trade"]["Currency"]["SmartContract"],
            "dex": r["Trade"]["Dex"]["ProtocolName"],
            "pool": r["Trade"]["Dex"]["SmartContract"],
            "trades": r["trades"],
            "buyers": r["buyers"],
            "sellers": r["sellers"],
            "buy_volume_usd": r["buy_volume"],
            "sell_volume_usd": r["sell_volume"],
            "last_trade": r["last_trade"],
        }
        for r in rows
    ]


@mcp.tool()
async def get_token_trades(token_address: str, limit: int = 20) -> list[dict]:
    """
    Get recent DEX trades for a specific token on BSC.
    Returns trade time, buyer/seller, amounts, prices, tx hash, and DEX info.
    """
    query = """
    query ($token: String!, $limit: Int) {
      EVM(network: bsc, dataset: combined) {
        DEXTrades(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Currency: {SmartContract: {is: $token}}
            }
          }
          orderBy: {descending: Block_Time}
          limit: {count: $limit}
        ) {
          Block {
            Time
          }
          Transaction {
            Hash
            From
          }
          Trade {
            Buy {
              Amount
              AmountInUSD
              Price
              PriceInUSD
              Currency {
                Symbol
                SmartContract
              }
              Buyer
            }
            Sell {
              Amount
              AmountInUSD
              Price
              Currency {
                Symbol
                SmartContract
              }
            }
            Dex {
              ProtocolName
              SmartContract
            }
          }
        }
      }
    }
    """
    data = await _bitquery(query, {"token": token_address, "limit": limit})
    rows = data.get("EVM", {}).get("DEXTrades", [])
    return [
        {
            "time": r["Block"]["Time"],
            "tx_hash": r["Transaction"]["Hash"],
            "maker": r["Transaction"]["From"],
            "buy_token": r["Trade"]["Buy"]["Currency"]["Symbol"],
            "buy_amount": r["Trade"]["Buy"]["Amount"],
            "buy_usd": r["Trade"]["Buy"]["AmountInUSD"],
            "price_usd": r["Trade"]["Buy"]["PriceInUSD"],
            "sell_token": r["Trade"]["Sell"]["Currency"]["Symbol"],
            "sell_amount": r["Trade"]["Sell"]["Amount"],
            "sell_usd": r["Trade"]["Sell"]["AmountInUSD"],
            "dex": r["Trade"]["Dex"]["ProtocolName"],
            "pool": r["Trade"]["Dex"]["SmartContract"],
        }
        for r in rows
    ]


@mcp.tool()
async def get_token_price(token_address: str) -> dict:
    """
    Get the current price and 24h OHLC for a token on BSC.
    Returns latest price in USD and BNB, plus 24-hour open/high/low/close and volume.
    """
    query = """
    query ($token: String!) {
      EVM(network: bsc, dataset: combined) {
        DEXTradeByTokens(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Currency: {SmartContract: {is: $token}}
              Side: {Currency: {SmartContract: {is: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"}}}
            }
          }
          orderBy: {descending: Block_Time}
          limit: {count: 1}
        ) {
          Trade {
            Currency {
              Name
              Symbol
            }
            PriceInUSD: Price(maximum: Block_Number)
            Price(maximum: Block_Number)
            high: Price(maximum: Trade_Price)
            low: Price(minimum: Trade_Price)
            open: Price(minimum: Block_Number)
            close: Price(maximum: Block_Number)
          }
          volume: sum(of: Trade_AmountInUSD)
          trades: count
          last_trade: maximum(of: Block_Time)
        }
      }
    }
    """
    data = await _bitquery(query, {"token": token_address})
    rows = data.get("EVM", {}).get("DEXTradeByTokens", [])
    if not rows:
        return {"error": "No trades found for this token"}
    r = rows[0]
    return {
        "name": r["Trade"]["Currency"]["Name"],
        "symbol": r["Trade"]["Currency"]["Symbol"],
        "price_usd": r["Trade"]["PriceInUSD"],
        "price_bnb": r["Trade"]["Price"],
        "high": r["Trade"]["high"],
        "low": r["Trade"]["low"],
        "open": r["Trade"]["open"],
        "close": r["Trade"]["close"],
        "volume_usd": r["volume"],
        "trades": r["trades"],
        "last_trade": r["last_trade"],
    }


@mcp.tool()
async def get_token_info(token_address: str) -> dict:
    """
    Get token details: name, symbol, total trades, unique traders, and buy/sell volume on BSC.
    """
    query = """
    query ($token: String!) {
      EVM(network: bsc, dataset: combined) {
        DEXTradeByTokens(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Currency: {SmartContract: {is: $token}}
            }
          }
        ) {
          Trade {
            Currency {
              Name
              Symbol
              SmartContract
            }
          }
          trades: count
          buyers: count(distinct: Trade_Buy_Buyer)
          sellers: count(distinct: Trade_Buy_Seller)
          buy_volume: sum(of: Trade_Buy_AmountInUSD)
          sell_volume: sum(of: Trade_Sell_AmountInUSD)
          first_trade: minimum(of: Block_Time)
          last_trade: maximum(of: Block_Time)
        }
      }
    }
    """
    data = await _bitquery(query, {"token": token_address})
    rows = data.get("EVM", {}).get("DEXTradeByTokens", [])
    if not rows:
        return {"error": "Token not found or no trades"}
    r = rows[0]
    return {
        "name": r["Trade"]["Currency"]["Name"],
        "symbol": r["Trade"]["Currency"]["Symbol"],
        "address": r["Trade"]["Currency"]["SmartContract"],
        "total_trades": r["trades"],
        "unique_buyers": r["buyers"],
        "unique_sellers": r["sellers"],
        "buy_volume_usd": r["buy_volume"],
        "sell_volume_usd": r["sell_volume"],
        "first_trade": r["first_trade"],
        "last_trade": r["last_trade"],
    }


@mcp.tool()
async def get_top_traders(token_address: str, limit: int = 10) -> list[dict]:
    """
    Get the top traders (by USD volume) for a specific token on BSC.
    Returns wallet address, buy/sell volume, and trade count.
    """
    query = """
    query ($token: String!, $limit: Int) {
      EVM(network: bsc, dataset: combined) {
        DEXTradeByTokens(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Currency: {SmartContract: {is: $token}}
            }
          }
          orderBy: {descendingByField: "volume"}
          limit: {count: $limit}
        ) {
          Trade {
            Buy {
              Buyer
            }
          }
          volume: sum(of: Trade_Buy_AmountInUSD)
          buy_volume: sum(of: Trade_Buy_AmountInUSD)
          sell_volume: sum(of: Trade_Sell_AmountInUSD)
          trades: count
        }
      }
    }
    """
    data = await _bitquery(query, {"token": token_address, "limit": limit})
    rows = data.get("EVM", {}).get("DEXTradeByTokens", [])
    return [
        {
            "wallet": r["Trade"]["Buy"]["Buyer"],
            "total_volume_usd": r["volume"],
            "buy_volume_usd": r["buy_volume"],
            "sell_volume_usd": r["sell_volume"],
            "trades": r["trades"],
        }
        for r in rows
    ]


@mcp.tool()
async def get_token_pairs(token_address: str) -> list[dict]:
    """
    Get all trading pairs and DEX pools for a specific token on BSC.
    Returns pair token, DEX name, pool address, trade count, and volume.
    """
    query = """
    query ($token: String!) {
      EVM(network: bsc, dataset: combined) {
        DEXTradeByTokens(
          where: {
            TransactionStatus: {Success: true}
            Trade: {
              Currency: {SmartContract: {is: $token}}
            }
          }
          orderBy: {descendingByField: "trades"}
        ) {
          Trade {
            Currency {
              Symbol
            }
            Side {
              Currency {
                Name
                Symbol
                SmartContract
              }
            }
            Dex {
              ProtocolName
              SmartContract
            }
          }
          trades: count
          volume: sum(of: Trade_AmountInUSD)
        }
      }
    }
    """
    data = await _bitquery(query, {"token": token_address})
    rows = data.get("EVM", {}).get("DEXTradeByTokens", [])
    return [
        {
            "token_symbol": r["Trade"]["Currency"]["Symbol"],
            "pair_symbol": r["Trade"]["Side"]["Currency"]["Symbol"],
            "pair_name": r["Trade"]["Side"]["Currency"]["Name"],
            "pair_address": r["Trade"]["Side"]["Currency"]["SmartContract"],
            "dex": r["Trade"]["Dex"]["ProtocolName"],
            "pool": r["Trade"]["Dex"]["SmartContract"],
            "trades": r["trades"],
            "volume_usd": r["volume"],
        }
        for r in rows
    ]


# ── Trade execution tools (web3 + PancakeSwap) ──────────────────────────────

@mcp.tool()
def get_wallet_balance(token_address: str | None = None) -> dict:
    """
    Get the wallet's BNB balance and optionally a token balance.
    If token_address is provided, also returns the token balance with symbol and decimals.
    """
    account, address = _get_wallet()
    if not account:
        return {"error": "WALLET_PRIVATE_KEY not configured"}

    bnb_balance = w3.eth.get_balance(address)
    result = {
        "wallet": address,
        "bnb_balance": str(w3.from_wei(bnb_balance, "ether")),
    }

    if token_address:
        token = w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
        )
        try:
            decimals = token.functions.decimals().call()
            raw_balance = token.functions.balanceOf(address).call()
            symbol = token.functions.symbol().call()
            allowance = token.functions.allowance(address, PANCAKE_ROUTER_V2).call()
            result["token"] = {
                "address": token_address,
                "symbol": symbol,
                "decimals": decimals,
                "balance": str(raw_balance / (10 ** decimals)),
                "raw_balance": str(raw_balance),
                "router_allowance": str(allowance / (10 ** decimals)),
            }
        except Exception as e:
            result["token_error"] = str(e)

    return result


@mcp.tool()
def get_swap_quote(token_address: str, amount_bnb: float) -> dict:
    """
    Get a quote for swapping BNB to a token via PancakeSwap V2.
    Returns expected token output amount and effective price.
    """
    try:
        token_cs = Web3.to_checksum_address(token_address)
        amount_in_wei = w3.to_wei(amount_bnb, "ether")
        path = [WBNB, token_cs]

        amounts_out = router.functions.getAmountsOut(amount_in_wei, path).call()
        token_out_raw = amounts_out[1]

        token_contract = w3.eth.contract(address=token_cs, abi=ERC20_ABI)
        decimals = token_contract.functions.decimals().call()
        symbol = token_contract.functions.symbol().call()

        token_out = token_out_raw / (10 ** decimals)

        return {
            "input_bnb": amount_bnb,
            "output_token": str(token_out),
            "output_raw": str(token_out_raw),
            "symbol": symbol,
            "decimals": decimals,
            "effective_price_bnb": str(amount_bnb / token_out) if token_out > 0 else "N/A",
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def swap_bnb_for_token(
    token_address: str,
    amount_bnb: float,
    slippage_pct: float = 10.0,
) -> dict:
    """
    Buy a token with BNB via PancakeSwap V2.
    Uses swapExactETHForTokensSupportingFeeOnTransferTokens for meme token compatibility.
    slippage_pct: maximum acceptable slippage in percent (default 10% for meme tokens).
    Returns transaction hash and status.
    """
    account, address = _get_wallet()
    if not account:
        return {"error": "WALLET_PRIVATE_KEY not configured"}

    try:
        token_cs = Web3.to_checksum_address(token_address)
        amount_in_wei = w3.to_wei(amount_bnb, "ether")
        path = [WBNB, token_cs]

        # Get expected output
        amounts_out = router.functions.getAmountsOut(amount_in_wei, path).call()
        min_out = int(amounts_out[1] * (1 - slippage_pct / 100))
        deadline = int(time.time()) + 300

        tx = router.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
            min_out, path, address, deadline
        ).build_transaction({
            "from": address,
            "value": amount_in_wei,
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "status": "success" if receipt["status"] == 1 else "failed",
            "tx_hash": tx_hash.hex(),
            "gas_used": receipt["gasUsed"],
            "block": receipt["blockNumber"],
            "amount_bnb": amount_bnb,
            "min_tokens_out": str(min_out),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def swap_token_for_bnb(
    token_address: str,
    token_amount: float,
    slippage_pct: float = 10.0,
) -> dict:
    """
    Sell a token for BNB via PancakeSwap V2.
    Uses swapExactTokensForETHSupportingFeeOnTransferTokens for meme token compatibility.
    Make sure to call approve_token first if needed.
    slippage_pct: maximum acceptable slippage in percent (default 10%).
    Returns transaction hash and status.
    """
    account, address = _get_wallet()
    if not account:
        return {"error": "WALLET_PRIVATE_KEY not configured"}

    try:
        token_cs = Web3.to_checksum_address(token_address)
        token_contract = w3.eth.contract(address=token_cs, abi=ERC20_ABI)
        decimals = token_contract.functions.decimals().call()
        amount_in_raw = int(token_amount * (10 ** decimals))

        path = [token_cs, WBNB]
        amounts_out = router.functions.getAmountsOut(amount_in_raw, path).call()
        min_bnb_out = int(amounts_out[1] * (1 - slippage_pct / 100))
        deadline = int(time.time()) + 300

        tx = router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
            amount_in_raw, min_bnb_out, path, address, deadline
        ).build_transaction({
            "from": address,
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "status": "success" if receipt["status"] == 1 else "failed",
            "tx_hash": tx_hash.hex(),
            "gas_used": receipt["gasUsed"],
            "block": receipt["blockNumber"],
            "tokens_sold": str(token_amount),
            "min_bnb_out": str(w3.from_wei(min_bnb_out, "ether")),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def approve_token(token_address: str) -> dict:
    """
    Approve PancakeSwap V2 Router to spend a token (unlimited allowance).
    Must be called before selling a token via swap_token_for_bnb.
    """
    account, address = _get_wallet()
    if not account:
        return {"error": "WALLET_PRIVATE_KEY not configured"}

    try:
        token_cs = Web3.to_checksum_address(token_address)
        token_contract = w3.eth.contract(address=token_cs, abi=ERC20_ABI)
        max_amount = 2**256 - 1

        tx = token_contract.functions.approve(
            PANCAKE_ROUTER_V2, max_amount
        ).build_transaction({
            "from": address,
            "gas": 100000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "status": "approved" if receipt["status"] == 1 else "failed",
            "tx_hash": tx_hash.hex(),
            "token": token_address,
            "spender": PANCAKE_ROUTER_V2,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
