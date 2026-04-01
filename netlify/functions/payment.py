"""
netlify/functions/payment.py
Netlify Function (Python) — Integração com a API SyncPayments.
Blindado contra falhas de Top-Level para Diagnóstico Profissional.
"""

import json
import sys
import traceback

def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Content-Type": "application/json",
    }

def handler(event, context):
    """
    Handler super blindado. Qualquer erro, incluindo de bibliotecas não instaladas,
    será capturado e retornado como JSON, não como página HTML.
    """
    # Preflight CORS rápido
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": cors_headers(), "body": ""}

    try:
        # Imports ocorrem dentro da função para evitar crashes na inicialização da Lambda
        import os
        import re
        import requests
        import io
        import base64

        # --- Constants e Configurações ---
        BASE_URL = "https://api.syncpayments.com.br/"
        SALE_PRICE_CENTS = 29700   # R$ 297,00
        PIX_DISCOUNT_PCT = 0.10    # 10%

        def clean_cpf(cpf: str) -> str:
            return re.sub(r"\D", "", cpf)

        def validate_cpf(cpf: str) -> bool:
            cpf = clean_cpf(cpf)
            if len(cpf) != 11 or cpf == cpf[0] * 11:
                return False
            for i in range(9, 11):
                s = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
                if int(cpf[i]) != ((s * 10) % 11) % 10:
                    return False
            return True

        class SyncPayBackend:
            def __init__(self):
                self.base_url = BASE_URL.strip("/")
                self.client_id = os.getenv("SYNCPAY_ID", os.environ.get("SYNCPAY_API_KEY", ""))
                self.client_secret = os.getenv("SYNCPAY_API", os.environ.get("SYNCPAY_API_KEY", ""))
                self.token = None

            def obter_token(self):
                url = f"{self.base_url}/api/partner/v1/auth-token"
                payload = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
                headers = {'Content-Type': 'application/json'}
                try:
                    res = requests.post(url, json=payload, headers=headers, timeout=10)
                    if res.status_code == 200:
                        self.token = res.json().get("access_token")
                        return self.token
                    else:
                        return None
                except Exception:
                    return None

            def gerar_pix_deposito(self, valor, nome, cpf, email):
                if not self.token:
                    if not self.obter_token():
                        return {"error": "Falha na autenticação (IDs inválidos ou API recusou)."}

                url = f"{self.base_url}/api/partner/v1/cash-in"
                payload = {
                    "amount": valor,
                    "description": f"Compra de {nome}",
                    "webhook_url": "https://seu-site.com/api/webhook",
                    "client": {
                        "name": nome,
                        "cpf": clean_cpf(cpf),
                        "email": email,
                        "phone": "11999999999"
                    }
                }
                headers = {
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                try:
                    res = requests.post(url, json=payload, headers=headers, timeout=15)
                    if res.status_code in [200, 201]:
                        return res.json()
                    else:
                        return {"error": f"Erro do gateway conectando ao Cash-in ({res.status_code}): {res.text}"}
                except Exception as e:
                    return {"error": f"Erro grave de conexão ao servidor gateway: {str(e)}"}

            def gerar_qrcode_base64(self, conteudo_pix):
                try:
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(conteudo_pix)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                    return f"data:image/png;base64,{img_str}"
                except Exception:
                    return ""

        # Inicio Processamento Real
        if event.get("httpMethod") != "POST":
            return {"statusCode": 405, "headers": cors_headers(), "body": json.dumps({"error": "Apenas POST."})}

        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Payload JSON do frontend corrompido."})}

        name = body.get("name", "").strip()
        email = body.get("email", "").strip().lower()
        cpf = body.get("cpf", "").strip()
        method = body.get("method", "pix").lower()

        if not name or not email or not cpf:
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Faltando dados de cliente."})}

        if not validate_cpf(cpf):
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "CPF provido não é um CPF válido."})}

        if method != "pix":
            return {"statusCode": 400, "headers": cors_headers(), "body": json.dumps({"error": "Suporte limitado ao PIX ativado."})}

        amount_cents = SALE_PRICE_CENTS
        if method == "pix":
            amount_cents = int(amount_cents * (1 - PIX_DISCOUNT_PCT))

        amount_float = amount_cents / 100.0

        syncpay = SyncPayBackend()
        data = syncpay.gerar_pix_deposito(valor=amount_float, nome=name, cpf=cpf, email=email)

        if isinstance(data, dict) and "error" in data:
            return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": data["error"]})}

        pix_text = data.get("pix_code") or data.get("qrcode") or ""
        pix_image = syncpay.gerar_qrcode_base64(pix_text) if pix_text else ""

        response_payload = {
            "success": True,
            "method": "pix",
            "amount_brl": amount_float,
            "payment_id": data.get("id", data.get("transaction_id")),
            "status": "pending",
            "pix": {
                "qr_code_image": pix_image, 
                "qr_code_text": pix_text,   
                "expires_at": None,
            }
        }

        return {
            "statusCode": 200,
            "headers": cors_headers(),
            "body": json.dumps(response_payload),
        }

    except ImportError as e:
        # Erro Clássico de dependências locais se a nuvem não resolveu o requirements
        err = [{"error_type": "ImportError", "message": str(e), "traceback": traceback.format_exc()}]
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": "Falha no empacotamento da Lambda Netlify. Biblioteca externa faltando.", "debug": err})}

    except Exception as e:
        # Erro genérico do Python formatado corretamente como JSON
        err = [{"error_type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}]
        return {"statusCode": 500, "headers": cors_headers(), "body": json.dumps({"error": "Runtime crash detalhado", "debug": err})}
