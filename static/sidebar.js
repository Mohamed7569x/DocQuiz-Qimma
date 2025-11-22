(function(){
    const sb = document.getElementById('sidebar');
    if (!sb) return;
  
    /* ===== Desktop mini state (persisted) ===== */
    function setMini(mini){
      if (mini) { sb.setAttribute('data-mini','1'); }
      else      { sb.removeAttribute('data-mini'); }
      localStorage.setItem('sidebarMini', mini ? '1' : '0');
    }
    setMini(localStorage.getItem('sidebarMini') === '1');
  
    // Optional external buttons (put in your topbar):
    // <button id="sidebarDesktopToggle">…</button>
    // <button id="sidebarToggle">…</button>  (mobile open)
    // <button id="sidebarClose">…</button>   (mobile close)
    const btnDesktop = document.getElementById('sidebarDesktopToggle');
    const btnOpen    = document.getElementById('sidebarToggle');
    const btnClose   = document.getElementById('sidebarClose');
  
    btnDesktop && btnDesktop.addEventListener('click', ()=> setMini(!sb.hasAttribute('data-mini')));
  
    /* ===== Hover expand in mini (desktop) ===== */
    sb.addEventListener('pointerenter', ()=>{
      if (window.innerWidth >= 1024 && sb.hasAttribute('data-mini')) sb.classList.add('hovering');
    });
    sb.addEventListener('pointerleave', ()=> sb.classList.remove('hovering'));
  
    /* ===== Mobile drawer ===== */
    function openMobile(){ sb.classList.remove('translate-x-full'); sb.classList.add('force-open'); }
    function closeMobile(){ sb.classList.add('translate-x-full'); sb.classList.remove('force-open'); }
    btnOpen  && btnOpen.addEventListener('click', openMobile);
    btnClose && btnClose.addEventListener('click', closeMobile);
    window.addEventListener('keydown', e=>{ if(e.key==='Escape') closeMobile(); });
    function scrub(){ if (window.innerWidth >= 1024) closeMobile(); }
    window.addEventListener('resize', scrub); scrub();
  
    /* ===== Accordion ===== */
    document.querySelectorAll('[data-accordion-trigger]').forEach(btn=>{
      const panel = document.querySelector(btn.getAttribute('data-target'));
      const chev  = btn.querySelector('[data-chevron]');
      btn.addEventListener('click', ()=>{
        const show = panel.classList.contains('hidden');
        panel.classList.toggle('hidden', !show);
        btn.dataset.open = show ? 'true' : 'false';
        if (chev) chev.style.transform = show ? 'rotate(180deg)' : '';
      });
    });
  
    /* ===== Active route ===== */
    function normalize(p){ try{ p = new URL(p, location.origin).pathname }catch{} return (p||'/').replace(/\/+$/,'') || '/' }
    const explicit = sb.getAttribute('data-active'); // from template variable `active`
    const current  = explicit ? normalize(explicit) : normalize(location.pathname);
  
    document.querySelectorAll('#sb-nav .nav-link').forEach(a=>{
      const r = a.getAttribute('data-route');
      if (r && normalize(r) === current){
        a.classList.add('active-nav');
  
        // open parent accordion if exists
        const panel = a.closest('[data-accordion-panel]');
        if (panel){
          panel.classList.remove('hidden');
          const trigger = document.querySelector(`[data-accordion-trigger][data-target="#${panel.id}"]`);
          const chev = trigger && trigger.querySelector('[data-chevron]');
          if (trigger){ trigger.dataset.open = 'true'; if (chev) chev.style.transform = 'rotate(180deg)'; }
        }
      }
    });
  
    /* ===== Logout stub (override in your app) ===== */
    window.logout = window.logout || function(){ alert('Logged out (stub). Wire to your auth endpoint.'); };
  })();
  