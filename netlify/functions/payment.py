"""
netlify/functions/payment.py
Netlify Function (Python) — Integração com a API SyncPay.
Responsável por processar pagamentos via Pix e Cartão de Crédito.
"""

import json
import os
import re
import requests


# ─── Configurações da SyncPay ─────────────────────────────────────────────────
SYNCPAY_API_URL = "https://api.syncpay.com.br/v1/payments"
SYNCPAY_API_KEY = os.environ.get("SYNCPAY_API", "")  # Definida no .env do Netlify

# Preços em centavos (fallback se não vier do request)
SALE_PRICE_CENTS = 29700   # R$ 297,00
PIX_DISCOUNT_PCT = 0.10    # 10%


# ─── Helpers ──────────────────────────────────────────────────────────────────

def clean_cpf(cpf: str) -> str:
    """Remove formatação do CPF."""
    return re.sub(r"\D", "", cpf)


def validate_cpf(cpf: str) -> bool:
    """Validação básica de CPF brasileiro."""
    cpf = clean_cpf(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        s = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
        if int(cpf[i]) != ((s * 10) % 11) % 10:
            return False
    return True


def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Content-Type": "application/json",
    }


# ─── Handler Principal ────────────────────────────────────────────────────────

def handler(event, context):
    # Preflight CORS
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": cors_headers(), "body": ""}

    if event.get("httpMethod") != "POST":
        return {
            "statusCode": 405,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Método não permitido."}),
        }

    # ── Parse do Body ─────────────────────────────────────────────────────────
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "JSON inválido."}),
        }

    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    cpf = body.get("cpf", "").strip()
    method = body.get("method", "pix").lower()
    card_number = body.get("card_number", "")
    card_expiry = body.get("card_expiry", "")
    card_cvv = body.get("card_cvv", "")
    card_holder = body.get("card_holder", "").strip()
    installments = int(body.get("installments", 1))

    # ── Validações ────────────────────────────────────────────────────────────
    if not name or not email or not cpf:
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Nome, email e CPF são obrigatórios."}),
        }

    if not validate_cpf(cpf):
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "CPF inválido."}),
        }

    if method not in ("pix", "credit_card"):
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Método de pagamento inválido."}),
        }

    # ── Cálculo de Valor ──────────────────────────────────────────────────────
    amount_cents = SALE_PRICE_CENTS
    if method == "pix":
        amount_cents = int(amount_cents * (1 - PIX_DISCOUNT_PCT))

    # ── Montagem do Payload SyncPay ───────────────────────────────────────────
    payload = {
        "amount": amount_cents,
        "currency": "BRL",
        "payment_method": method,
        "customer": {
            "name": name,
            "email": email,
            "cpf": clean_cpf(cpf),
        },
        "description": "PulseX Pro — TECNOLOGIA BR",
        "statement_descriptor": "TECNOLOGIA BR",
        "metadata": {
            "product": "pulsex_pro",
            "source": "landing_page",
        },
    }

    if method == "credit_card":
        payload["card"] = {
            "number": re.sub(r"\D", "", card_number),
            "expiry_month": card_expiry.split("/")[0].strip() if "/" in card_expiry else "",
            "expiry_year": card_expiry.split("/")[1].strip() if "/" in card_expiry else "",
            "cvv": card_cvv,
            "holder_name": card_holder,
            "installments": installments,
        }

    # ── Chamada à API SyncPay ─────────────────────────────────────────────────
    try:
        resp = requests.post(
            SYNCPAY_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {SYNCPAY_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        data = resp.json()
    except requests.exceptions.Timeout:
        return {
            "statusCode": 504,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Timeout ao conectar com o gateway de pagamento."}),
        }
    except Exception as e:
        return {
            "statusCode": 502,
            "headers": cors_headers(),
            "body": json.dumps({"error": f"Erro de comunicação: {str(e)}"}),
        }

    if resp.status_code not in (200, 201):
        error_msg = data.get("message") or data.get("error") or "Erro no gateway de pagamento."
        return {
            "statusCode": resp.status_code,
            "headers": cors_headers(),
            "body": json.dumps({"error": error_msg}),
        }

    # ── Resposta ao Frontend ──────────────────────────────────────────────────
    response_payload = {
        "success": True,
        "method": method,
        "amount_brl": amount_cents / 100,
        "payment_id": data.get("id"),
        "status": data.get("status"),
    }

    if method == "pix":
        pix = data.get("pix", {})
        response_payload["pix"] = {
            "qr_code_image": pix.get("qr_code_image"),   # Base64 PNG
            "qr_code_text": pix.get("qr_code_text"),     # Copia e Cola
            "expires_at": pix.get("expires_at"),
        }
    else:
        response_payload["card"] = {
            "authorized": data.get("status") == "authorized",
            "last4": data.get("card", {}).get("last4"),
        }

    return {
        "statusCode": 200,
        "headers": cors_headers(),
        "body": json.dumps(response_payload),
    }
