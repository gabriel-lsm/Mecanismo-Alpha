/**
 * script.js — PulseX Pro
 * DOM logic, stock counter, payment method switching,
 * Pix discount calculation, API calls and QR code display.
 */

'use strict';

/* ── Helpers ──────────────────────────────────────────────────── */

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function fmt(amount) {
  return amount.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function showToast(message, type = 'success') {
  const toast = $('#toast');
  toast.textContent = (type === 'success' ? '✅ ' : '❌ ') + message;
  toast.className = `toast toast--${type} visible`;
  setTimeout(() => { toast.className = 'toast'; }, 4500);
}

/* ── Intersection Observer (fade-in) ─────────────────────────── */
function initFadeIn() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  $$('.fade-in').forEach(el => observer.observe(el));
}

/* ── Stock Counter ────────────────────────────────────────────── */
function initStock() {
  const stock    = CONFIG.product.stock;
  const countEl  = $('#stock-count');
  const fillEl   = $('#stock-fill');
  const finalEl  = $('#final-stock-count');

  // Simulate small random decrement every 2–6 minutes
  let current = stock;

  function update() {
    if (countEl)  countEl.textContent = `Apenas ${current} unidades`;
    if (finalEl)  finalEl.textContent = `${current} unidades`;
    if (fillEl) {
      const pct = Math.max(5, (current / 100) * 100);
      fillEl.style.width = pct + '%';
      fillEl.parentElement.setAttribute('aria-valuenow', current);
    }
  }

  update();

  const tick = () => {
    const delay = (Math.random() * 4 + 2) * 60 * 1000; // 2–6 min
    setTimeout(() => {
      if (current > 2) {
        current -= 1;
        update();
        tick();
      }
    }, delay);
  };
  tick();
}

/* ── Payment Tabs ─────────────────────────────────────────────── */
let currentMethod = 'pix';

function initPaymentTabs() {
  const tabs        = $$('.payment-tab');
  const pixPanel    = $('#panel-pix');
  const cardPanel   = $('#panel-card');
  const discountRow = $('#pix-discount-row');
  const pixTotalRow = $('#pix-total-row');
  const totalEl     = $('#order-total');

  const salePrice = CONFIG.product.salePrice;
  const pixPrice  = salePrice * (1 - CONFIG.product.pixDiscount);

  function selectMethod(method) {
    currentMethod = method;

    tabs.forEach(t => {
      const active = t.dataset.method === method;
      t.classList.toggle('active', active);
      t.setAttribute('aria-selected', String(active));
    });

    if (method === 'pix') {
      pixPanel.style.display   = 'block';
      cardPanel.style.display  = 'none';
      discountRow.style.display = 'flex';
      pixTotalRow.style.display = 'flex';
      if (totalEl) totalEl.textContent = fmt(pixPrice);
    } else {
      pixPanel.style.display   = 'none';
      cardPanel.style.display  = 'block';
      discountRow.style.display = 'none';
      pixTotalRow.style.display = 'none';
      if (totalEl) totalEl.textContent = fmt(salePrice);
    }
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => selectMethod(tab.dataset.method));
  });

  // Init with pix
  selectMethod('pix');
}

/* ── CPF Mask ─────────────────────────────────────────────────── */
function initCPFMask() {
  const cpfInput = $('#input-cpf');
  if (!cpfInput) return;
  cpfInput.addEventListener('input', function () {
    let v = this.value.replace(/\D/g, '').slice(0, 11);
    if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
    else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
    else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
    this.value = v;
  });
}

/* ── Card Number Mask ─────────────────────────────────────────── */
function initCardMask() {
  const cardInput = $('#input-card-number');
  if (!cardInput) return;
  cardInput.addEventListener('input', function () {
    let v = this.value.replace(/\D/g, '').slice(0, 16);
    this.value = v.replace(/(\d{4})(?=\d)/g, '$1 ');
  });

  const expInput = $('#input-card-expiry');
  if (!expInput) return;
  expInput.addEventListener('input', function () {
    let v = this.value.replace(/\D/g, '').slice(0, 4);
    if (v.length > 2) v = v.replace(/(\d{2})(\d{1,2})/, '$1 / $2');
    this.value = v;
  });
}

/* ── Validation ───────────────────────────────────────────────── */
function validateCPF(cpf) {
  cpf = cpf.replace(/\D/g, '');
  if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
  for (let i = 9; i <= 10; i++) {
    let sum = 0;
    for (let j = 0; j < i; j++) sum += parseInt(cpf[j]) * (i + 1 - j);
    if (parseInt(cpf[i]) !== ((sum * 10) % 11) % 10) return false;
  }
  return true;
}

function showError(inputId, errorId, show) {
  const input = $(`#${inputId}`);
  const error = $(`#${errorId}`);
  if (!input || !error) return;
  input.classList.toggle('error', show);
  error.style.display = show ? 'block' : 'none';
}

function validateForm() {
  let valid = true;

  const name = $('#input-name').value.trim();
  if (name.split(' ').length < 2 || name.length < 5) {
    showError('input-name', 'error-name', true); valid = false;
  } else showError('input-name', 'error-name', false);

  const email = $('#input-email').value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showError('input-email', 'error-email', true); valid = false;
  } else showError('input-email', 'error-email', false);

  const cpf = $('#input-cpf').value.trim();
  if (!validateCPF(cpf)) {
    showError('input-cpf', 'error-cpf', true); valid = false;
  } else showError('input-cpf', 'error-cpf', false);

  return valid;
}

/* ── Pix Timer ────────────────────────────────────────────────── */
let pixTimerInterval = null;

function startPixTimer(seconds = 1800) {
  const timerEl = $('#pix-timer');
  let remaining = seconds;

  clearInterval(pixTimerInterval);
  pixTimerInterval = setInterval(() => {
    remaining--;
    const m = String(Math.floor(remaining / 60)).padStart(2, '0');
    const s = String(remaining % 60).padStart(2, '0');
    if (timerEl) timerEl.textContent = `${m}:${s}`;
    if (remaining <= 0) {
      clearInterval(pixTimerInterval);
      if (timerEl) timerEl.textContent = 'EXPIRADO';
      timerEl.style.color = 'var(--red)';
    }
  }, 1000);
}

/* ── Pix QR Display ───────────────────────────────────────────── */
function showPixResult(data) {
  const form      = $('#checkout-form');
  const pixResult = $('#pix-result');
  const qrImg     = $('#pix-qr-img');
  const codeText  = $('#pix-code-text');

  if (form)      form.style.display       = 'none';
  if (pixResult) pixResult.classList.add('visible');

  if (qrImg && data.pix?.qr_code_image) {
    const src = data.pix.qr_code_image.startsWith('data:')
      ? data.pix.qr_code_image
      : `data:image/png;base64,${data.pix.qr_code_image}`;
    qrImg.src = src;
  }

  if (codeText && data.pix?.qr_code_text) {
    codeText.textContent = data.pix.qr_code_text;
  }

  startPixTimer();
  updateSteps(3);
}

/* ── Card Success Display ─────────────────────────────────────── */
function showCardSuccess() {
  const form    = $('#checkout-form');
  const success = $('#card-success');
  if (form)    form.style.display   = 'none';
  if (success) success.classList.add('visible');
  updateSteps(3);
}

/* ── Step Indicators ──────────────────────────────────────────── */
function updateSteps(activeStep) {
  for (let i = 1; i <= 3; i++) {
    const el = $(`#step-${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < activeStep) el.classList.add('done');
    if (i === activeStep) el.classList.add('active');
  }
}

/* ── Pix Copy Button ──────────────────────────────────────────── */
function initPixCopy() {
  const copyBtn  = $('#pix-copy-btn');
  const codeText = $('#pix-code-text');
  if (!copyBtn || !codeText) return;

  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(codeText.textContent);
      copyBtn.textContent = '✓ Copiado!';
      copyBtn.classList.add('copied');
      showToast('Código Pix copiado!', 'success');
      setTimeout(() => {
        copyBtn.textContent = 'Copiar';
        copyBtn.classList.remove('copied');
      }, 3000);
    } catch {
      showToast('Erro ao copiar. Copie manualmente.', 'error');
    }
  });
}

/* ── Form Submit ──────────────────────────────────────────────── */
function initForm() {
  const form   = $('#checkout-form');
  const btn    = $('#btn-submit');
  if (!form || !btn) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    updateSteps(2);
    btn.disabled = true;
    btn.classList.add('loading');

    const payload = {
      name:   $('#input-name').value.trim(),
      email:  $('#input-email').value.trim().toLowerCase(),
      cpf:    $('#input-cpf').value.trim(),
      method: currentMethod,
    };

    if (currentMethod === 'credit_card') {
      payload.card_number  = $('#input-card-number')?.value ?? '';
      payload.card_expiry  = $('#input-card-expiry')?.value ?? '';
      payload.card_cvv     = $('#input-card-cvv')?.value ?? '';
      payload.card_holder  = $('#input-card-holder')?.value ?? '';
      payload.installments = parseInt($('#input-installments')?.value ?? '1');
    }

    try {
      const resp = await fetch(CONFIG.payment.apiUrl, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });

      const data = await resp.json();

      if (!resp.ok || !data.success) {
        throw new Error(data.error || 'Erro ao processar pagamento.');
      }

      if (currentMethod === 'pix') {
        showPixResult(data);
      } else {
        showCardSuccess();
        showToast('Pagamento aprovado com sucesso! 🎉', 'success');
      }
    } catch (err) {
      showToast(err.message || 'Erro de conexão. Tente novamente.', 'error');
      updateSteps(1);
    } finally {
      btn.disabled = false;
      btn.classList.remove('loading');
    }
  });
}

/* ── FAQ Accordion ────────────────────────────────────────────── */
function initFAQ() {
  $$('.faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item     = btn.closest('.faq-item');
      const isOpen   = item.classList.contains('open');
      // Close all
      $$('.faq-item').forEach(i => {
        i.classList.remove('open');
        i.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
      });
      if (!isOpen) {
        item.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
  });
}

/* ── Footer Year ──────────────────────────────────────────────── */
function initFooterYear() {
  const el = $('#footer-year');
  if (el) el.textContent = new Date().getFullYear();
}

/* ── Smooth scroll for internal CTA links ────────────────────── */
function initSmoothScroll() {
  $$('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = $(a.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ── Bootstrap ────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initFadeIn();
  initStock();
  initPaymentTabs();
  initCPFMask();
  initCardMask();
  initPixCopy();
  initForm();
  initFAQ();
  initFooterYear();
  initSmoothScroll();
});
