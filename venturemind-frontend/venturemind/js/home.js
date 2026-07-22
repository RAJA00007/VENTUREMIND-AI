/* ============================================================================
   Home page interactions — only loaded by index.html:
   collapsible What/How sections, the 3D agent-priority pipeline wheel,
   scroll reveal + tilt, the hero particle network, left index-nav
   scrollspy, scroll progress bar / back-to-top, and the nav profile
   dropdown (reads AccountStore so it reflects sign-in state from login.html).
   Requires account-store.js to be loaded first.
   ============================================================================ */

  // ---------- collapsible sections ----------
  function toggleSection(id){
    const el = document.getElementById(id);
    const wasOpen = el.classList.contains('open');
    document.querySelectorAll('.numbered-section').forEach(s => s.classList.remove('open'));
    if(!wasOpen) el.classList.add('open');
  }

  // ---------- pipeline: agents, per-company-type priority order, and 3D elliptical wheel ----------
  const AGENTS = {
    research:   {name:'Research',   desc:'Product, mission, team', abbr:'RES'},
    github:     {name:'GitHub',     desc:'Code, commits, contributors', abbr:'GH'},
    market:     {name:'Market',     desc:'TAM, CAGR, trends', abbr:'MKT'},
    competitor: {name:'Competitor', desc:'Positioning, SWOT', abbr:'CMP'},
    founder:    {name:'Founder',    desc:'Background, track record', abbr:'FDR'},
    finance:    {name:'Finance',    desc:'Funding, valuation', abbr:'FIN'},
    risk:       {name:'Risk',       desc:'Legal, security exposure', abbr:'RSK'},
    committee:  {name:'Committee',  desc:'Weighs every agent\u2019s findings into one recommendation.', abbr:'CMT'}
  };

  const ORDERS = {
    tech:    ['github','research','market','founder','competitor','finance','risk','committee'],
    nontech: ['finance','market','founder','competitor','research','risk','github','committee'],
    hybrid:  ['research','market','github','finance','competitor','founder','risk','committee']
  };

  const NOTES = {
    tech: 'For a technical company, the GitHub agent leads: the codebase is weighted as the primary evidence, ahead of the pitch. The Committee agent is the only one permitted to combine findings into a recommendation, and it always shows its work.',
    nontech: 'For a non technical company, Finance and Market agents lead the weighting, and GitHub carries the least influence when there is little code to evaluate. The Committee agent still has final say, and always shows its work.',
    hybrid: 'For a hybrid company, evidence is weighted more evenly across product, market, and code before anything is prioritized. The Committee agent reconciles all seven views into one recommendation, and always shows its work.'
  };

  const OUTER_KEYS = ['research','github','market','competitor','founder','finance','risk'];
  const TILT_DEG = 60; // must match .wheel-tilt rotateX in CSS

  function ordinalSuffix(n){
    const s = ['th','st','nd','rd'], v = n % 100;
    return n + (s[(v-20)%10] || s[v] || s[0]);
  }
  function rankLabel(i, key){
    if(key === 'committee') return 'Synthesis';
    if(i === 0) return 'Leads';
    return ordinalSuffix(i+1) + ' priority';
  }

  let currentPipelineType = 'tech';
  let wheelTimer = null;
  let wheelStepIndex = 0;
  let wheelSpinDeg = 0;
  let spinRAF = null;

  // Builds the 3D scaffolding once: a tilted, spinning group holding a true
  // circular ring + nodes. Because it's real 3D (perspective + preserve-3d),
  // the circle reads as an ellipse and nodes at the "back" recede naturally —
  // no faked ellipse math needed. Nodes are billboarded (counter-rotated) so
  // their text always faces the viewer while the ring keeps turning.
  function buildWheelDOM(){
    const wheel = document.getElementById('pipelineWheel');
    let root = document.getElementById('wheelRoot');
    if(root) root.remove();

    root = document.createElement('div');
    root.id = 'wheelRoot';
    root.style.position = 'absolute';
    root.style.inset = '0';
    wheel.appendChild(root);

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('id', 'wheelLines');
    svg.style.position = 'absolute'; svg.style.inset = '0';
    svg.style.width = '100%'; svg.style.height = '100%';
    svg.style.pointerEvents = 'none';
    root.appendChild(svg);

    const tilt = document.createElement('div');
    tilt.className = 'wheel-tilt';
    root.appendChild(tilt);

    const spin = document.createElement('div');
    spin.className = 'wheel-spin';
    spin.id = 'wheelSpin';
    tilt.appendChild(spin);

    const ring = document.createElement('div');
    ring.className = 'wheel-ring-3d';
    ring.id = 'wheelRing3d';
    spin.appendChild(ring);

    OUTER_KEYS.forEach(key => {
      const a = AGENTS[key];
      const node = document.createElement('div');
      node.className = 'wheel-node';
      node.dataset.key = key;
      node.innerHTML = `<div class="wheel-node-inner"><div class="wn-dot">${a.abbr}</div><div class="wn-name">${a.name}</div><div class="wn-tag"></div></div>`;
      spin.appendChild(node);

      const line = document.createElementNS(svgNS, 'line');
      line.dataset.key = key;
      line.setAttribute('stroke', 'var(--line-soft)');
      line.setAttribute('stroke-width', '1');
      svg.appendChild(line);
    });

    const center = document.createElement('div');
    center.className = 'wheel-center';
    center.id = 'wheelCenter';
    center.innerHTML = `<div class="wc-eyebrow">Focusing</div><div class="wc-name" id="wcName">Committee</div><div class="wc-desc" id="wcDesc">Weighs every agent\u2019s findings into one recommendation.</div>`;
    root.appendChild(center);

    layoutRing();
    positionNodes(currentPipelineType);

    // Click a node to focus it directly — pauses the auto-cycle briefly.
    spin.querySelectorAll('.wheel-node').forEach(node => {
      node.addEventListener('click', () => {
        clearInterval(wheelTimer);
        focusWheelNode(node.dataset.key);
        wheelTimer = setInterval(stepWheel, 1700);
      });
    });
  }

  // Explicit ellipse: independent x/y radii (wider than tall) so the ring
  // reads as a big oval even before the 3D tilt is applied.
  function wheelRadii(){
    const wheel = document.getElementById('pipelineWheel');
    const rect = wheel.getBoundingClientRect();
    return { rx: rect.width * 0.47, ry: rect.height * 0.40 };
  }
  function wheelRadius(){ // kept for anything reading a single scalar radius
    const {rx, ry} = wheelRadii();
    return Math.max(rx, ry);
  }

  function layoutRing(){
    const {rx, ry} = wheelRadii();
    const ring = document.getElementById('wheelRing3d');
    if(!ring) return;
    ring.style.width = (2 * rx) + 'px';
    ring.style.height = (2 * ry) + 'px';
    ring.style.marginLeft = (-rx) + 'px';
    ring.style.marginTop = (-ry) + 'px';
  }

  // Places each agent node around the true ellipse according to its current
  // priority rank (rank 0 = top/"Leads"). This is what makes the order the
  // wheel reorders itself — not just the labels — whenever the tab changes.
  function positionNodes(type){
    const order = ORDERS[type].filter(k => k !== 'committee');
    const {rx, ry} = wheelRadii();
    order.forEach((key, i) => {
      const angleDeg = -90 + i * (360 / order.length);
      const rad = angleDeg * Math.PI / 180;
      const x = rx * Math.cos(rad);
      const y = ry * Math.sin(rad);
      const node = document.querySelector(`.wheel-node[data-key="${key}"]`);
      if(node) node.style.transform = `translate3d(${x}px, ${y}px, 0px)`;
    });
  }

  // Runs every frame while the wheel is on screen: spins the ring, keeps
  // node labels billboarded upright, and re-derives the connector lines
  // from actual on-screen positions (simplest way to stay correct through
  // both the spin and the reordering transition).
  function tickWheel(){
    wheelSpinDeg = (wheelSpinDeg + 0.12) % 360;
    const spin = document.getElementById('wheelSpin');
    if(spin) spin.style.transform = `rotateZ(${wheelSpinDeg}deg)`;

    document.querySelectorAll('.wheel-node-inner').forEach(inner => {
      inner.style.transform = `rotateZ(${-wheelSpinDeg}deg) rotateX(${-TILT_DEG}deg)`;
    });

    updateWheelLines();
    spinRAF = requestAnimationFrame(tickWheel);
  }
  function startSpin(){ if(!spinRAF) spinRAF = requestAnimationFrame(tickWheel); }
  function stopSpin(){ if(spinRAF){ cancelAnimationFrame(spinRAF); spinRAF = null; } }

  function updateWheelLines(){
    const wheel = document.getElementById('pipelineWheel');
    const center = document.getElementById('wheelCenter');
    if(!wheel || !center) return;
    const wheelRect = wheel.getBoundingClientRect();
    const centerRect = center.getBoundingClientRect();
    const cx = centerRect.left + centerRect.width / 2 - wheelRect.left;
    const cy = centerRect.top + centerRect.height / 2 - wheelRect.top;

    OUTER_KEYS.forEach(key => {
      const node = document.querySelector(`.wheel-node[data-key="${key}"]`);
      const line = document.querySelector(`#wheelLines line[data-key="${key}"]`);
      if(!node || !line) return;
      const r = node.getBoundingClientRect();
      const nx = r.left + r.width / 2 - wheelRect.left;
      const ny = r.top + r.height / 2 - wheelRect.top;
      line.setAttribute('x1', cx); line.setAttribute('y1', cy);
      line.setAttribute('x2', nx); line.setAttribute('y2', ny);
    });
  }

  function setRankTags(type){
    const order = ORDERS[type].filter(k => k !== 'committee');
    order.forEach((key, i) => {
      const tagEl = document.querySelector(`.wheel-node[data-key="${key}"] .wn-tag`);
      if(tagEl) tagEl.textContent = rankLabel(i, key);
    });
  }

  function renderPipeline(type){
    currentPipelineType = type;
    document.querySelectorAll('.ptab').forEach(t => t.classList.toggle('active', t.dataset.type === type));
    document.getElementById('pipelineNote').textContent = NOTES[type];
    setRankTags(type);
    positionNodes(type);
    startWheelCycle();
  }

  function setPipelineType(type){ renderPipeline(type); }

  function startWheelCycle(){
    clearInterval(wheelTimer);
    wheelStepIndex = 0;
    stepWheel();
    wheelTimer = setInterval(stepWheel, 1700);
  }

  function stepWheel(){
    const order = ORDERS[currentPipelineType];
    const key = order[wheelStepIndex % order.length];
    focusWheelNode(key);
    wheelStepIndex++;
  }

  function focusWheelNode(key){
    document.querySelectorAll('.wheel-node').forEach(n => n.classList.remove('focused'));
    document.querySelectorAll('#wheelLines line').forEach(l => l.setAttribute('stroke', 'var(--line-soft)'));
    const center = document.getElementById('wheelCenter');
    const eyebrow = center.querySelector('.wc-eyebrow');

    if(key === 'committee'){
      center.classList.add('pulsing');
      eyebrow.textContent = 'Synthesis';
      document.getElementById('wcName').textContent = 'Committee';
      document.getElementById('wcDesc').textContent = AGENTS.committee.desc;
    } else {
      center.classList.remove('pulsing');
      eyebrow.textContent = 'Focusing';
      const node = document.querySelector(`.wheel-node[data-key="${key}"]`);
      if(node) node.classList.add('focused');
      const line = document.querySelector(`#wheelLines line[data-key="${key}"]`);
      if(line) line.setAttribute('stroke', 'var(--green)');
      const a = AGENTS[key];
      document.getElementById('wcName').textContent = a.name;
      document.getElementById('wcDesc').textContent = a.desc;
    }
  }

  buildWheelDOM();
  window.addEventListener('resize', () => { layoutRing(); positionNodes(currentPipelineType); });

  const pipelineObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if(entry.isIntersecting){
        layoutRing();
        renderPipeline(currentPipelineType);
        startSpin();
      } else {
        clearInterval(wheelTimer);
        stopSpin();
      }
    });
  }, {threshold:0.3});
  pipelineObserver.observe(document.getElementById('pipeline'));

  // ---------- "window popping out" reveal — replays every time you scroll past, up or down ----------
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const el = entry.target;
      if(entry.isIntersecting){
        el.classList.add('in');
        if(el.classList.contains('window-section') && !el.dataset.tiltEnabled){
          el.dataset.tiltEnabled = '1';
          setTimeout(() => enableTilt(el), 950);
        }
      } else {
        el.classList.remove('in');
      }
    });
  }, {threshold:0.12, rootMargin:'0px 0px -60px 0px'});


  document.querySelectorAll('.reveal, .window-section, .sub-item, .text-reveal').forEach(el => revealObserver.observe(el));

  // ---------- headline word-mask stagger ----------
  document.querySelectorAll('.megaline .word-inner').forEach((el, i) => {
    el.style.transitionDelay = (i * 0.06) + 's';
  });

  // ---------- subtle 3D tilt on window cards, after they've popped in ----------
  function enableTilt(el){
    el.style.transition = 'transform .2s ease-out, box-shadow .3s ease';
    el.addEventListener('mousemove', (e) => {
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      const rx = -((y - r.height/2) / (r.height/2)) * 2.5;
      const ry = ((x - r.width/2) / (r.width/2)) * 2.5;
      el.style.transform = `perspective(1400px) rotateX(${rx}deg) rotateY(${ry}deg) scale(1.004)`;
    });
    el.addEventListener('mouseleave', () => {
      el.style.transform = 'perspective(1400px) rotateX(0deg) rotateY(0deg) scale(1)';
    });
  }

  // ---------- hero network canvas: agent nodes + connecting lines ----------
  function initHeroNetwork(){
    const canvas = document.getElementById('heroNetwork');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    let w, h, points = [], dpr = Math.min(window.devicePixelRatio || 1, 2);

    function resize(){
      const rect = canvas.parentElement.getBoundingClientRect();
      w = rect.width; h = rect.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      generatePoints();
    }

    function generatePoints(){
      points = [];
      const cx = w * 0.66, cy = h * 0.46;
      const count = Math.max(50, Math.min(140, Math.floor((w * h) / 9500)));
      for(let i = 0; i < count; i++){
        const ang = Math.random() * Math.PI * 2;
        const rad = Math.pow(Math.random(), 1.7) * Math.min(w, h) * 0.46;
        points.push({
          x: cx + Math.cos(ang) * rad + (Math.random() - 0.5) * 50,
          y: cy + Math.sin(ang) * rad * 0.82 + (Math.random() - 0.5) * 50,
          r: Math.random() * 2.2 + 0.6,
          baseOpacity: Math.random() * 0.45 + 0.12,
          phase: Math.random() * Math.PI * 2,
          driftX: (Math.random() - 0.5) * 0.18,
          driftY: (Math.random() - 0.5) * 0.18
        });
      }
    }

    let t = 0;
    function draw(){
      t += 0.008;
      ctx.clearRect(0, 0, w, h);
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const rgb = isDark ? '90,230,150' : '15,90,50';
      for(let i = 0; i < points.length; i++){
        for(let j = i + 1; j < points.length; j++){
          const a = points[i], b = points[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const dist = Math.sqrt(dx*dx + dy*dy);
          if(dist < 64){
            ctx.strokeStyle = `rgba(${rgb},${(1 - dist/64) * (isDark ? 0.22 : 0.14)})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      points.forEach(p => {
        p.x += Math.sin(t + p.phase) * p.driftX;
        p.y += Math.cos(t + p.phase) * p.driftY;
        const o = Math.max(p.baseOpacity + Math.sin(t * 1.5 + p.phase) * 0.1, 0.05);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},${o})`;
        ctx.fill();
      });
      requestAnimationFrame(draw);
    }

    window.addEventListener('resize', resize);
    resize();
    draw();
  }
  initHeroNetwork();

  // ---------- left index nav: scrollspy active state ----------
  const indexLinks = document.querySelectorAll('.index-nav a[href^="#"]');
  const spySections = Array.from(indexLinks).map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const spyObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if(entry.isIntersecting){
        const id = '#' + entry.target.id;
        indexLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === id));
      }
    });
  }, {threshold:0.4});
  spySections.forEach(s => spyObserver.observe(s));

  // ---------- scroll progress bar, parallax grid, back-to-top ----------
  let scrollTicking = false;
  function onScrollFrame(){
    const doc = document.documentElement;
    const scrollTop = window.scrollY || doc.scrollTop;
    const scrollHeight = doc.scrollHeight - doc.clientHeight;
    const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
    document.getElementById('scrollProgress').style.width = pct + '%';
    document.getElementById('backToTop').classList.toggle('show', scrollTop > 700);
    doc.style.setProperty('--grid-shift', (scrollTop * 0.04) + 'px');
    scrollTicking = false;
  }
  window.addEventListener('scroll', () => {
    if(!scrollTicking){
      requestAnimationFrame(onScrollFrame);
      scrollTicking = true;
    }
  });
  onScrollFrame();


// ---------- nav profile icon: swaps the "Log in" buttons for an account icon once signed in ----------
// Reads AccountStore (localStorage) rather than an in-memory array, since
// sign-in now happens on the separate login.html page via a real navigation.
function updateNavProfile(){
  const acc = AccountStore.getActiveAccount();
  const navLogin = document.getElementById('navLoginBtn');
  const heroLogin = document.getElementById('heroLoginBtn');
  const navProfile = document.getElementById('navProfile');

  if(acc){
    const initial = acc.name.trim()[0].toUpperCase();
    document.getElementById('profileInitial').textContent = initial;
    document.getElementById('profileMenuAvatar').textContent = initial;
    document.getElementById('profileMenuName').textContent = acc.name;
    document.getElementById('profileMenuEmail').textContent = acc.email;
    document.getElementById('profileMenuTag').textContent = acc.type === 'business' ? 'Business' : 'Personal';

    if(navLogin) navLogin.classList.add('hidden');
    if(heroLogin) {
      heroLogin.textContent = "Go to Dashboard";
      heroLogin.href = "dashboard.html";
      heroLogin.classList.remove('hidden');
    }
    if(navProfile) navProfile.classList.remove('hidden');
  } else {
    if(navLogin) navLogin.classList.remove('hidden');
    if(heroLogin) heroLogin.classList.remove('hidden');
    if(navProfile) navProfile.classList.add('hidden');
    const menu = document.getElementById('profileMenu');
    if(menu) menu.classList.remove('open');
  }
}

function toggleProfileMenu(e){
  e.stopPropagation();
  document.getElementById('profileMenu').classList.toggle('open');
}
document.addEventListener('click', function(e){
  const menu = document.getElementById('profileMenu');
  if(menu && menu.classList.contains('open') && !e.target.closest('.nav-profile')){
    menu.classList.remove('open');
  }
});

// "Sign out" from the nav dropdown just clears the store and updates this
// page in place — no navigation needed.
function logoutAllFromNav(){
  document.getElementById('profileMenu').classList.remove('open');
  AccountStore.clear();
  updateNavProfile();
}

updateNavProfile();
