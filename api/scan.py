from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import requests


def scan_solana_token(token_mint):
    url = f"https://api.rugcheck.xyz/v1/tokens/{token_mint}/report?reportType=basic"
    try:
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}, 500

    creator = data.get('creator', 'Unknown')
    creator_balance = data.get('creatorBalance', 0)
    token_info = data.get('token', {})
    supply = token_info.get('supply', 0) / (10 ** token_info.get('decimals', 0)) if token_info.get('supply') else 0
    dev_hold_pct = (creator_balance / supply * 100) if supply > 0 else 0

    is_bond = token_mint.lower().endswith('pump')
    launch_vs_bond = "dev bond more than launch" if is_bond else "dev launch more than bond"
    bond_rating = "good" if is_bond else "not good"

    if creator_balance == 0:
        dev_rating = "good (sold)"
        dev_score = 3
    else:
        dev_rating = "good (hold <4%)" if dev_hold_pct < 4 else "bad (hold >=4%)"
        dev_score = 3 if dev_hold_pct < 4 else -1

    top_holders = data.get('topHolders', [])
    top10_pct = sum(h['pct'] for h in top_holders[:10])
    top_rating = "good" if top10_pct < 20 else "bad"
    top_score = 2 if top10_pct < 20 else -2

    bundles_pct = sum(h['pct'] for h in top_holders if h.get('insider', False))
    if bundles_pct < 10:
        bundles_rating = "safe"
        bundles_score = 3
    elif bundles_pct < 20:
        bundles_rating = "careful"
        bundles_score = 1
    else:
        bundles_rating = "be careful"
        bundles_score = -2

    score = 5 + dev_score + top_score + bundles_score + (2 if is_bond else -1)
    score = max(1, min(10, score))

    rating = "untrusted" if score <= 4 else "be careful" if score <= 7 else "acceptable"

    result = {
        "token_mint": token_mint,
        "dev_wallet": creator,
        "dev_holdings_pct": round(dev_hold_pct, 2),
        "dev_rating": dev_rating,
        "launch_vs_bond": launch_vs_bond,
        "bond_rating": bond_rating,
        "bundles_pct": round(bundles_pct, 2),
        "bundles_rating": bundles_rating,
        "top10_pct": round(top10_pct, 2),
        "top10_rating": top_rating,
        "score": score,
        "rating": rating.upper(),
        "top_10_holders": [
            {"owner": h["owner"], "pct": round(h["pct"], 2), "insider": h.get("insider", False)}
            for h in top_holders[:10]
        ]
    }

    return result, 200


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_path.query)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if parsed_path.path == '/api/scan':
            mint = params.get('mint', [None])[0]
            if not mint:
                result = {"error": "Missing ?mint= parameter"}
                self.wfile.write(json.dumps(result).encode())
                return

            result, status = scan_solana_token(mint.strip())
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
        else:
            self.wfile.write(b'{"message": "Solana Token Scanner API\\nUse: /api/scan?mint=TOKEN_MINT_ADDRESS"}')
