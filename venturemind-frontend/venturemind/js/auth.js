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

function submitLogin(){
  const email = document.getElementById('loginEmail').value.trim();
  const pass = document.getElementById('loginPassword').value.trim();
  if(!email || !pass){ document.getElementById('loginError').classList.add('show'); return; }
  const name = email.split('@')[0].replace(/[._]/g,' ').replace(/\b\w/g, c => c.toUpperCase());
  addAccount({name, email, type: modalType});
}

function submitSignup(){
  const name = document.getElementById('signupName').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  const pass = document.getElementById('signupPassword').value.trim();
  const company = document.getElementById('signupCompany').value.trim();
  if(!name || !email || !pass){ document.getElementById('signupError').classList.add('show'); return; }
  const displayName = modalType==='business' && company ? `${name} · ${company}` : name;
  addAccount({name: displayName, email, type: modalType});
}

function addAccount(acc){
  accounts.push(acc);
  activeIndex = accounts.length - 1;
  AccountStore.save(accounts, activeIndex);
  // Go straight to the main site after logging in/signing up — not to the
  // account panel. The account panel is still kept ready in the background
  // for next time this page is opened while already signed in (or reached
  // via "Manage account" from the main site's nav).
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

// ---------- boot: show the account switcher if already signed in, otherwise the auth forms ----------
(function initAuthPage(){
  if(activeIndex >= 0 && accounts[activeIndex]){
    showAccountView();
  } else {
    showLogin();
  }
})();
