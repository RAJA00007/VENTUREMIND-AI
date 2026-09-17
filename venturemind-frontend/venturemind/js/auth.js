/* ============================================================================
   Login page logic — only loaded by login.html.
   Handles the login/signup forms and the signed-in account switcher, backed
   by AccountStore (localStorage) so state survives a real page navigation
   between login.html and index.html. There's no real backend here — this is
   a front-end mock of an auth flow.
   Requires account-store.js to be loaded first.
   ============================================================================ */

let accounts = AccountStore.getAccounts();
let activeIndex = AccountStore.getActiveIndex();
let modalType = 'personal';

function setAccountType(type){
  modalType = type;
  document.getElementById('tabPersonal').classList.toggle('active', type==='personal');
  document.getElementById('tabBusiness').classList.toggle('active', type==='business');
  document.getElementById('typeLabelIntro').textContent = type;
  document.getElementById('companyField').classList.toggle('hidden', type!=='business');
  document.getElementById('signupEmailLabel').textContent = type==='business' ? 'Work email' : 'Email';
}

function showLogin(){
  document.getElementById('loginForm').classList.remove('hidden');
  document.getElementById('signupForm').classList.add('hidden');
  document.getElementById('loginError').classList.remove('show');
}
function showSignup(){
  document.getElementById('signupForm').classList.remove('hidden');
  document.getElementById('loginForm').classList.add('hidden');
  document.getElementById('signupError').classList.remove('show');
}

const API_BASE_URL = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

async function submitLogin(){
  const email = document.getElementById('loginEmail').value.trim();
  const pass = document.getElementById('loginPassword').value.trim();
  const errorEl = document.getElementById('loginError');

  if(!email || !pass){
    if(errorEl) { errorEl.textContent = 'Please fill in all fields'; errorEl.classList.add('show'); }
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pass })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Login failed');
    }

    const data = await res.json();
    localStorage.setItem('auth_token', data.access_token);
    const name = data.user_name || email.split('@')[0];
    addAccount({ name, email: data.email, type: modalType });
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = err.message || 'Login failed. Check server connection.';
      errorEl.classList.add('show');
    }
  }
}

async function quickDemoLogin() {
  const email = 'demo@venturemind.ai';
  const pass = 'DemoPassword123!';
  const name = 'Venture Partner';
  const btn = document.getElementById('demoLoginBtn');
  if (btn) btn.textContent = 'Signing in...';

  try {
    let res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pass })
    });

    if (!res.ok) {
      // Auto register if account not found
      res = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          email: email,
          password: pass,
          account_type: 'business',
          company: 'VentureMind Capital'
        })
      });
    }

    if (!res.ok) {
      throw new Error('Could not authenticate demo user');
    }

    const data = await res.json();
    localStorage.setItem('auth_token', data.access_token);
    addAccount({ name: name, email: data.email, type: 'business' });
  } catch (err) {
    console.error('Demo login error:', err);
    if (btn) btn.textContent = '⚡ 1-Click Demo Login';
    const errorEl = document.getElementById('loginError');
    if (errorEl) {
      errorEl.textContent = 'Demo login failed. Make sure backend is running.';
      errorEl.classList.add('show');
    }
  }
}

async function submitSignup(){
  const name = document.getElementById('signupName').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  const pass = document.getElementById('signupPassword').value.trim();
  const company = document.getElementById('signupCompany').value.trim();
  const errorEl = document.getElementById('signupError');

  if(!name || !email || !pass){
    if(errorEl) { errorEl.textContent = 'Please fill in all required fields'; errorEl.classList.add('show'); }
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        email,
        password: pass,
        account_type: modalType,
        company: company || null
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Registration failed');
    }

    const data = await res.json();
    localStorage.setItem('auth_token', data.access_token);
    const displayName = modalType==='business' && company ? `${name} · ${company}` : name;
    addAccount({ name: displayName, email: data.email, type: modalType });
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = err.message || 'Registration failed. Check server connection.';
      errorEl.classList.add('show');
    }
  }
}

function addAccount(acc){
  accounts.push(acc);
  activeIndex = accounts.length - 1;
  AccountStore.save(accounts, activeIndex);
  location.href = 'dashboard.html';
}

function showAccountView(){
  document.getElementById('authView').classList.add('hidden');
  document.getElementById('accountView').classList.remove('hidden');
  renderAccountView();
}

function showAuthForNewAccount(){
  document.getElementById('accountView').classList.add('hidden');
  document.getElementById('authView').classList.remove('hidden');
  ['loginEmail','loginPassword','signupName','signupCompany','signupEmail','signupPassword'].forEach(id=>{
    const el = document.getElementById(id); if(el) el.value = '';
  });
  showLogin();
}

function renderAccountView(){
  const active = accounts[activeIndex];
  if(!active) return;
  document.getElementById('avatarInitial').textContent = active.name.trim()[0].toUpperCase();
  document.getElementById('acctName').textContent = active.name;
  document.getElementById('acctEmail').textContent = active.email;
  document.getElementById('acctTag').textContent = active.type === 'business' ? 'Business' : 'Personal';

  const list = document.getElementById('accountList');
  list.innerHTML = '';
  accounts.forEach((acc, i) => {
    const row = document.createElement('div');
    row.className = 'account-row' + (i===activeIndex ? ' active' : '');
    row.onclick = () => { activeIndex = i; AccountStore.save(accounts, activeIndex); renderAccountView(); };
    row.innerHTML = `<div class="mini-avatar">${acc.name.trim()[0].toUpperCase()}</div>
      <div class="r-name">${acc.name}<span>${acc.type==='business'?'Business':'Personal'} · ${acc.email}</span></div>
      ${i===activeIndex ? '<span class="check">✓</span>' : ''}`;
    list.appendChild(row);
  });
}

function logoutAll(){
  accounts = [];
  activeIndex = -1;
  AccountStore.clear();
  document.getElementById('accountView').classList.add('hidden');
  document.getElementById('authView').classList.remove('hidden');
  showLogin();
}

function openInNewTab(){
  window.open(window.location.href, '_blank');
}

async function continueToDashboard() {
  const btn = document.querySelector('.continue-btn');
  if (btn) btn.textContent = 'Launching Dashboard...';

  let token = localStorage.getItem('auth_token');
  const active = accounts[activeIndex];

  if (!token && active) {
    try {
      const pass = 'Password123!';
      let res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: active.email, password: pass })
      });

      if (!res.ok) {
        res = await fetch(`${API_BASE_URL}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: active.name || active.email.split('@')[0],
            email: active.email,
            password: pass,
            account_type: active.type || 'personal',
            company: null
          })
        });
      }

      if (res.ok) {
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('auth_token', token);
      }
    } catch (err) {
      console.warn('Auto-session error:', err);
    }
  }

  if (token) {
    location.href = 'dashboard.html';
  } else {
    if (btn) btn.textContent = 'Continue to VentureMind AI';
    showAuthForNewAccount();
  }
}

// ---------- boot: show the account switcher if already signed in, otherwise the auth forms ----------
(function initAuthPage(){
  if(activeIndex >= 0 && accounts[activeIndex]){
    showAccountView();
  } else {
    showLogin();
  }
})();
