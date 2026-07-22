/* ============================================================================
   Shared visual effects — glossy click ripple and the cursor splash trail.
   Loaded by both index.html and login.html. Requires <canvas id="cursorSplash">
   to be present in the page for the splash trail.
   ============================================================================ */

// ---------- glossy click ripple, delegated across buttons/tabs/nodes/cards ----------
document.addEventListener('click', function(e){
  const el = e.target.closest('.btn, .ptab, .sub-item, .theme-toggle, .continue-btn, .submit, .type-tab, .panel-action, .account-row');
  if(!el) return;
  el.classList.add('ripple-host');
  const rect = el.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 1.6;
  const span = document.createElement('span');
  span.className = 'ripple';
  span.style.width = span.style.height = size + 'px';
  span.style.left = (e.clientX - rect.left - size / 2) + 'px';
  span.style.top = (e.clientY - rect.top - size / 2) + 'px';
  el.appendChild(span);
  span.addEventListener('animationend', () => span.remove());
});

// ---------- cursor splash / ripple effect on the background ----------
(function(){
  const canvas = document.getElementById('cursorSplash');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  let ripples = [];
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let lastSplash = 0;

  function resizeSplash(){
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    canvas.style.width = window.innerWidth + 'px';
    canvas.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resizeSplash);
  resizeSplash();

  function addRipple(x, y){
    ripples.push({x, y, r:0, alpha:0.35, maxR: 60 + Math.random()*40});
  }

  window.addEventListener('mousemove', (e) => {
    const now = performance.now();
    if(now - lastSplash > 45){ // throttle
      addRipple(e.clientX, e.clientY);
      lastSplash = now;
    }
  });
  window.addEventListener('touchmove', (e) => {
    if(e.touches && e.touches[0]){
      addRipple(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, {passive:true});

  function drawSplash(){
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    ripples.forEach(rp => {
      rp.r += 1.6;
      rp.alpha *= 0.955;
      ctx.beginPath();
      ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI*2);
      ctx.strokeStyle = `rgba(22,163,74,${Math.max(rp.alpha,0)})`;
      ctx.lineWidth = 1.4;
      ctx.stroke();
    });
    ripples = ripples.filter(rp => rp.alpha > 0.01 && rp.r < rp.maxR + 30);
    requestAnimationFrame(drawSplash);
  }
  drawSplash();
})();
