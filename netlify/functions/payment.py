"""
netlify/functions/payment.py
Netlify Function (Python) — Integração com a API SyncPayments.
Responsável por processar pagamentos via Pix (novo fluxo autenticado).
"""

import json
import os
import re
import requests
import io
import base64

# --- Constants e Configurações ---
BASE_URL = "https://api.syncpayments.com.br/"

# Preços em centavos (fallback se não vier do request)
SALE_PRICE_CENTS = 29700   # R$ 297,00
PIX_DISCOUNT_PCT = 0.10    # 10%

# --- Classe Backend SyncPayments (Baseada no script validado) ---
class SyncPayBackend:
    def __init__(self):
        self.base_url = BASE_URL.strip("/")
        self.client_id = os.getenv("SYNCPAY_ID", os.environ.get("SYNCPAY_API_KEY", ""))
        self.client_secret = os.getenv("SYNCPAY_API", os.environ.get("SYNCPAY_API_KEY", ""))
        self.token = None

    def obter_token(self):
        """Passo 1: Autentica na API para ganhar um token temporário"""
        url = f"{self.base_url}/api/partner/v1/auth-token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                self.token = response.json().get("access_token")
                print("🔑 Token obtido com sucesso!")
                return self.token
            else:
                print(f"❌ Erro na autenticação ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            print(f"💥 Falha catastrófica ao conectar no Token: {e}")
            return None

    def gerar_pix_deposito(self, valor, nome, cpf, email):
        """Passo 2: Usa o token para gerar a cobrança PIX"""
        if not self.token:
            if not self.obter_token():
                return {"error": "Falha na autenticação. Verifique suas credenciais."}

        url = f"{self.base_url}/api/partner/v1/cash-in"
        
        payload = {
            "amount": valor,
            "description": f"Compra de {nome}",
            "webhook_url": "https://seu-site.com/api/webhook",
            "client": {
                "name": nome,
                "cpf": clean_cpf(cpf),
                "email": email,
                "phone": "11999999999"  # Fixo com 11 dígitos conforme validado
            }
        }

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        try:
            print(f"📡 Solicitando PIX de R$ {valor}...")
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code in [200, 201]:
                print("✅ PIX GERADO!")
                return response.json()
            else:
                erro_msg = f"Erro ao gerar PIX ({response.status_code}): {response.text}"
                print(f"❌ {erro_msg}")
                return {"error": erro_msg}
        except Exception as e:
            msg = f"💥 Erro na conexão do Cash-in: {e}"
            print(msg)
            return {"error": msg}

    def gerar_qrcode_base64(self, conteudo_pix):
        """Alternativa para gerar a imagem base64 na própria Netlify function."""
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(conteudo_pix)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
        except ImportError:
            print("⚠️ Biblioteca 'qrcode' não encontrada. Retornando vazio para a imagem.")
            return ""

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

def process_payment(event, context):
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

    if method != "pix":
        # Bloqueando CC por enquanto já que a homologação atual é PIX via SyncPayments
        return {
            "statusCode": 400,
            "headers": cors_headers(),
            "body": json.dumps({"error": "Método de pagamento não suportado nesta integração."}),
        }

    # ── Cálculo de Valor ──────────────────────────────────────────────────────
    amount_cents = SALE_PRICE_CENTS
    if method == "pix":
        amount_cents = int(amount_cents * (1 - PIX_DISCOUNT_PCT))

    # O script usa valor em float (ex: 1.50) em vez de centavos.
    amount_float = amount_cents / 100.0

    # ── Integração SyncPayBackend ─────────────────────────────────────────────
    syncpay = SyncPayBackend()
    data = syncpay.gerar_pix_deposito(valor=amount_float, nome=name, cpf=cpf, email=email)

    if "error" in data:
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": data["error"]}),
        }

    # ── Resposta ao Frontend ──────────────────────────────────────────────────
    # O objeto devolvido pela API SyncPayments possivelmente contém o campo pix_code
    pix_text = data.get("pix_code") or data.get("qrcode") or ""
    pix_image = syncpay.gerar_qrcode_base64(pix_text) if pix_text else ""

    response_payload = {
        "success": True,
        "method": "pix",
        "amount_brl": amount_float,
        "payment_id": data.get("id") or data.get("transaction_id"),
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

def handler(event, context):
    try:
        return process_payment(event, context)
    except Exception as e:
        # Captura qualquer erro não tratado na função e retorna JSON para evitar erro de frontend
        return {
            "statusCode": 500,
            "headers": cors_headers(),
            "body": json.dumps({"error": f"Erro interno no servidor: {str(e)}"}),
        }
