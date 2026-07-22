/* ============================================================================
   Dark mode toggle — shared by index.html and login.html.
   Theme choice is persisted to localStorage under 'vm-theme', so switching
   it on one page carries over to the other on next visit.
   ============================================================================ */

function applyTheme(theme){
  if(theme === 'dark') document.documentElement.setAttribute('data-theme','dark');
  else document.documentElement.removeAttribute('data-theme');
  document.querySelectorAll('#themeToggle, #themeToggleLogin').forEach(btn => {
    btn.textContent = theme === 'dark' ? '☀' : '☾';
  });
  try{ localStorage.setItem('vm-theme', theme); }catch(e){}
}

function toggleTheme(){
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  applyTheme(isDark ? 'light' : 'dark');
}

(function initTheme(){
  let saved = null;
  try{ saved = localStorage.getItem('vm-theme'); }catch(e){}
  applyTheme(saved === 'dark' ? 'dark' : 'light');
})();
