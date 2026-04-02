const QRCode = require('qrcode');

const BASE_URL = "https://api.syncpayments.com.br";
// Preços do produto (Thrusting Cannon King - Leten)
const SALE_PRICE_CENTS = 12990; // R$ 129,90
const PIX_DISCOUNT_PCT = 0.10;

exports.handler = async (event, context) => {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
  };

  // 1: CORS
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers, body: "" };
  }

  // Se não for POST
  if (event.httpMethod !== "POST") {
    return { 
      statusCode: 405, 
      headers, 
      body: JSON.stringify({ error: "Método não permitido. Utilize POST." }) 
    };
  }

  try {
    const body = JSON.parse(event.body || "{}");
    const { name, email, cpf, phone, method = "pix" } = body;

    // Validação Básica
    if (!name || !email || !cpf) {
      return { 
        statusCode: 400, 
        headers, 
        body: JSON.stringify({ error: "Faltando dados obrigatórios (Nome, E-mail, CPF)." }) 
      };
    }

    if (method !== "pix") {
      return { 
        statusCode: 400, 
        headers, 
        body: JSON.stringify({ error: "Apenas pagamento PIX é suportado nesta versão." }) 
      };
    }

    // Tratamento dos dados para SyncPay
    const cleanCpf = cpf.replace(/\D/g, "");
    
    let amountCents = SALE_PRICE_CENTS;
    if (method === "pix") {
      amountCents = Math.floor(amountCents * (1 - PIX_DISCOUNT_PCT));
    }
    const amountFloat = amountCents / 100.0;

    const clientId = process.env.SYNCPAY_ID || process.env.SYNCPAY_API_KEY;
    const clientSecret = process.env.SYNCPAY_API || process.env.SYNCPAY_API_KEY;

    if (!clientId || !clientSecret) {
      return { 
        statusCode: 500, 
        headers, 
        body: JSON.stringify({ error: "Chaves da SyncPay ausentes na configuração do Netlify." }) 
      };
    }

    // --- Passo 1: Autenticar para ganhar o Token ---
    const authRes = await fetch(`${BASE_URL}/api/partner/v1/auth-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
    });
    
    if (!authRes.ok) {
       return { 
         statusCode: 500, 
         headers, 
         body: JSON.stringify({ error: "Falha na autenticação da credencial com a SyncPayments." }) 
       };
    }
    const authData = await authRes.json();
    const token = authData.access_token;

    // --- Passo 2: Gerar o PIX (Cash-in) ---
    const cashinRes = await fetch(`${BASE_URL}/api/partner/v1/cash-in`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({
        amount: amountFloat,
        description: `Compra de ${name}`,
        webhook_url: "https://seu-site.com/api/webhook", // opcional/fake, a API exige
        client: {
          name: name,
          cpf: cleanCpf,
          email: email,
          phone: (phone || "11999999999").replace(/\D/g, "") || "11999999999"
        }
      })
    });

    const cashinData = await cashinRes.json();
    
    if (!cashinRes.ok) {
        return { 
          statusCode: cashinRes.status, 
          headers, 
          body: JSON.stringify({ error: `Erro na geração SyncPayments: ${JSON.stringify(cashinData)}` }) 
        };
    }

    // --- Passo 3: Geração do QRCode a partir da String Pix (Copia e Cola) ---
    const pixText = cashinData.pix_code || cashinData.qrcode || "";
    let pixImage = "";
    
    if (pixText) {
      try {
        // qrcode package devolve o link formatado -> data:image/png;base64,...
        pixImage = await QRCode.toDataURL(pixText); 
      } catch (e) {
        console.error("Erro renderizando QRCode base64 localmente", e);
      }
    }

    // Resposta final que o Frontend espera
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        success: true,
        method: "pix",
        amount_brl: amountFloat,
        payment_id: cashinData.id || cashinData.transaction_id,
        status: "pending",
        pix: {
          qr_code_image: pixImage,
          qr_code_text: pixText,
          expires_at: null
        }
      })
    };

  } catch (err) {
    // Blindagem de alto nível para erros obscuros de Node ou runtime
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        error: "Runtime execution crash", 
        detail: err.message, 
        stack: err.stack 
      })
    };
  }
};
