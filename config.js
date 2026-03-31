/**
 * config.js — Configurações globais do produto.
 * Altere aqui para ajustar preços, textos e links sem tocar em outros arquivos.
 */

const CONFIG = {
  product: {
    name: "PulseX Pro",
    tagline: "Tecnologia de prazer automação premium",
    originalPrice: 997.00,    // Preço de ancoragem
    salePrice: 297.00,        // Preço de venda
    pixDiscount: 0.10,        // 10% desconto Pix
    internationalPrice: 180,  // Preço em USD (referência "gringa")
    currency: "BRL",
    stock: 14,                // Estoque para contador dinâmico
  },

  invoice: {
    displayName: "TECNOLOGIA BR",  // Nome discreto na fatura
    packageNote: "Embalagem sem logos ou identificação externa",
  },

  shipping: {
    free: true,
    label: "Frete Grátis & Rastreado",
    eta: "3 a 7 dias úteis",
  },

  payment: {
    apiUrl: "/.netlify/functions/payment",
    methods: ["pix", "credit_card"],
  },

  links: {
    whatsapp: "https://wa.me/5511999999999",
    instagram: "",
    privacyPolicy: "#privacidade",
  },

  meta: {
    title: "PulseX Pro | Gadget Premium de Bem-Estar Masculino",
    description:
      "O mesmo gadget vendido por US$ 180 nos EUA — agora disponível no Brasil por importação direta. Frete grátis e embalagem 100% discreta.",
    keywords:
      "pulsex pro, gadget masculino, bem-estar, automação, discrição, frete grátis",
    ogImage: "assets/og-image.jpg",
  },
};
