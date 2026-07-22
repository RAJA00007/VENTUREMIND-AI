/* ============================================================================
   Account store — small localStorage-backed persistence layer shared by
   index.html (nav profile icon) and login.html (auth + account switcher).

   This site has no real backend, so "signed in" state is mocked entirely in
   the browser. Persisting it to localStorage (rather than a plain in-memory
   array, like an earlier single-file version of this site did) is what lets
   the signed-in state survive an actual navigation between the two pages.
   ============================================================================ */

const AccountStore = {
  ACCOUNTS_KEY: 'vm-accounts',
  ACTIVE_KEY: 'vm-active-index',

  getAccounts(){
    try{
      const raw = localStorage.getItem(this.ACCOUNTS_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    }catch(e){ return []; }
  },

  getActiveIndex(){
    try{
      const raw = localStorage.getItem(this.ACTIVE_KEY);
      if(raw === null) return -1;
      const n = parseInt(raw, 10);
      return Number.isNaN(n) ? -1 : n;
    }catch(e){ return -1; }
  },

  save(accounts, activeIndex){
    try{
      localStorage.setItem(this.ACCOUNTS_KEY, JSON.stringify(accounts));
      localStorage.setItem(this.ACTIVE_KEY, String(activeIndex));
    }catch(e){}
  },

  clear(){
    try{
      localStorage.removeItem(this.ACCOUNTS_KEY);
      localStorage.removeItem(this.ACTIVE_KEY);
    }catch(e){}
  },

  getActiveAccount(){
    const accounts = this.getAccounts();
    const i = this.getActiveIndex();
    return (i >= 0 && accounts[i]) ? accounts[i] : null;
  }
};
