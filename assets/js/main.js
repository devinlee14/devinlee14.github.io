/* Shared behaviour: nav, smooth scroll, reveals, hero animation, chart theme */
(() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const doc = document.documentElement;

  /* ---------- always open a page at the top (e.g. after "Next project") ---------- */
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  const toTop = () => {
    if (location.hash.length > 1) return;
    window.scrollTo(0, 0);
    try { document.documentElement.scrollIntoView({ block: "start" }); } catch (e) {}
  };
  toTop();
  window.addEventListener("pageshow", toTop);

  /* ---------- smooth scrolling (Lenis) ---------- */
  let lenis = null;
  if (!reduce && window.Lenis) {
    lenis = new Lenis({ duration: 1.15, easing: (t) => 1 - Math.pow(1 - t, 4), smoothWheel: true });
    const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
    requestAnimationFrame(raf);
  }
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const id = a.getAttribute("href");
      if (id.length < 2) return;
      const el = document.querySelector(id);
      if (!el) return;
      e.preventDefault();
      closeMenu();
      lenis ? lenis.scrollTo(el, { offset: -70 }) : el.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    });
  });

  /* ---------- nav: background after scroll, hide on scroll down ---------- */
  const nav = document.querySelector(".nav");
  let lastY = 0;
  const onScroll = () => {
    const y = window.scrollY;
    if (!nav) return;
    nav.classList.toggle("scrolled", y > 30);
    nav.classList.toggle("hide", y > 400 && y > lastY && !nav.classList.contains("menu-open"));
    lastY = y;
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const menuBtn = document.querySelector(".menu-btn");
  const links = document.querySelector(".nav-links");
  function closeMenu() {
    if (!links) return;
    links.classList.remove("open");
    nav && nav.classList.remove("menu-open");
    menuBtn && menuBtn.setAttribute("aria-expanded", "false");
  }
  menuBtn && menuBtn.addEventListener("click", () => {
    const open = !links.classList.contains("open");
    links.classList.toggle("open", open);
    nav.classList.toggle("menu-open", open);
    menuBtn.setAttribute("aria-expanded", String(open));
  });

  /* ---------- language switch (English / Indonesian) ---------- */
  const store = { get: () => { try { return localStorage.getItem("lang"); } catch (e) { return null; } },
                  set: (v) => { try { localStorage.setItem("lang", v); } catch (e) {} } };
  function setLang(lang) {
    document.querySelectorAll("[data-id]").forEach((el) => {
      if (el.dataset.en === undefined) el.dataset.en = el.innerHTML;
      el.innerHTML = lang === "id" ? el.dataset.id : el.dataset.en;
    });
    doc.lang = lang;
    document.querySelectorAll(".lang-toggle").forEach((b) => {
      const [en, id] = b.querySelectorAll("span");
      en.classList.toggle("on", lang === "en"); id.classList.toggle("on", lang === "id");
      b.setAttribute("aria-label", lang === "id" ? "Switch language to English" : "Ganti bahasa ke Bahasa Indonesia");
    });
    window.dispatchEvent(new CustomEvent("langchange", { detail: lang }));
  }
  window.currentLang = () => doc.lang === "id" ? "id" : "en";
  document.querySelectorAll(".lang-toggle").forEach((b) => b.addEventListener("click", () => {
    const next = window.currentLang() === "id" ? "en" : "id";
    store.set(next); setLang(next);
  }));
  if (store.get() === "id") setLang("id");

  /* ---------- reveal on scroll ---------- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

  window.addEventListener("load", () => {
    doc.classList.add("loaded");
    const target = location.hash.length > 1 && document.querySelector(location.hash);
    if (target) setTimeout(() => (lenis ? lenis.scrollTo(target, { offset: -70, immediate: true }) : target.scrollIntoView()), 60);
    else toTop();
  });
  setTimeout(() => doc.classList.add("loaded"), 1200); // fallback if a font stalls

  /* ---------- hero: noisy data settling into a validated trend ---------- */
  const canvas = document.getElementById("data-canvas");
  if (canvas) heroAnimation(canvas, reduce);

  /* ---------- chart theme ---------- */
  if (window.Chart) {
    const C = window.Chart;
    C.defaults.font.family = '"IBM Plex Sans", system-ui, sans-serif';
    C.defaults.font.size = 12;
    C.defaults.color = "#7f93a1";
    C.defaults.borderColor = "rgba(168,196,214,0.10)";
    C.defaults.maintainAspectRatio = false;
    C.defaults.animation.duration = reduce ? 0 : 1100;
    C.defaults.animation.easing = "easeOutQuart";
    C.defaults.plugins.legend.display = false;
    Object.assign(C.defaults.plugins.tooltip, {
      backgroundColor: "#192a36", borderColor: "rgba(168,196,214,0.26)", borderWidth: 1,
      titleColor: "#e8eef2", bodyColor: "#b0c0cb", padding: 10, cornerRadius: 8,
      displayColors: true, boxWidth: 9, boxHeight: 9, boxPadding: 4, usePointStyle: true,
      titleFont: { weight: "600" },
    });
    C.defaults.elements.line.borderWidth = 2;
    C.defaults.elements.point.radius = 0;
    C.defaults.elements.point.hoverRadius = 5;
    C.defaults.elements.bar.borderRadius = 4;
    C.defaults.scale.grid.drawTicks = false;
    C.defaults.scale.ticks.padding = 8;
    C.defaults.scale.border = { display: false };
  }
})();

/* Palette + helpers available to page scripts */
window.Viz = {
  c: { teal: "#14a08d", amber: "#c48214", blue: "#5e80da", rose: "#d05e82", text: "#e8eef2", muted: "#7f93a1", grid: "rgba(168,196,214,0.10)" },
  fmt: (n, d = 0) => Number(n).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }),
  compact: (n) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n),
  load: (path) => fetch(path).then((r) => r.json()),
  /* draw a chart only when it scrolls into view, so its animation is seen */
  whenVisible(el, draw) {
    if (!el) return;
    const ob = new IntersectionObserver((es) => {
      if (es[0].isIntersecting) { ob.disconnect(); draw(); }
    }, { threshold: 0.25 });
    ob.observe(el);
  },
  /* sequential teal scale for heatmaps: v in [0, 1] */
  seq(v) {
    const a = [26, 42, 54], b = [20, 160, 141];
    const t = Math.max(0, Math.min(1, v));
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t)).join(",")})`;
  },
};

function heroAnimation(canvas, reduce) {
  const ctx = canvas.getContext("2d");
  let W, H, dpr, pts = [], start = null, mouse = { x: -999, y: -999 };
  const N = 150;
  const teal = [79, 209, 188], amber = [232, 176, 79];

  // on narrow screens keep the animation in the top band, behind the portrait
  const band = (y) => (W > 960 ? y : Math.max(H * 0.03, y * 0.55 - H * 0.08));
  function target(i) {
    // monthly-looking series: growth trend + seasonality + small noise
    const t = i / (N - 1);
    const trend = 0.62 - t * 0.34;
    const season = Math.sin(t * Math.PI * 6) * 0.05 + Math.sin(t * Math.PI * 17) * 0.012;
    const x0 = W > 960 ? 0.5 : 0.04, span = W > 960 ? 0.48 : 0.92;
    return { x: W * (x0 + t * span), y: band(H * (trend + season)) };
  }
  function seed() {
    pts = [];
    for (let i = 0; i < N; i++) {
      const tg = target(i);
      const flagged = Math.random() < 0.16;
      pts.push({
        tx: tg.x, ty: tg.y,
        x: W * ((W > 960 ? 0.46 : 0.02) + Math.random() * (W > 960 ? 0.52 : 0.96)),
        y: flagged ? band(H * (Math.random() < 0.5 ? 0.08 + Math.random() * 0.15 : 0.78 + Math.random() * 0.15)) : tg.y + (Math.random() - 0.5) * H * (W > 960 ? 0.42 : 0.14),
        flagged, delay: 0.25 + (i / N) * 1.1 + Math.random() * 0.25,
        r: flagged ? 3.4 : 2.2 + Math.random() * 1.2, phase: Math.random() * Math.PI * 2,
      });
      pts[i].sx = pts[i].x; pts[i].sy = pts[i].y;
    }
  }
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
    if (reduce) draw(99);
  }
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));

  function draw(time) {
    ctx.clearRect(0, 0, W, H);
    // faint grid
    ctx.strokeStyle = "rgba(168,196,214,0.06)";
    ctx.lineWidth = 1;
    for (let g = 1; g < 6; g++) {
      const y = (H / 6) * g;
      ctx.beginPath(); ctx.moveTo(W > 960 ? W * 0.46 : 0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    // trend line draws once points have mostly settled
    const lineT = Math.max(0, Math.min(1, (time - 1.6) / 1.4));
    if (lineT > 0) {
      ctx.beginPath();
      const upto = Math.floor(ease(lineT) * (N - 1));
      for (let i = 0; i <= upto; i++) {
        const p = pts[i];
        i ? ctx.lineTo(p.tx, p.ty + Math.sin(time * 0.8 + i * 0.12) * 2) : ctx.moveTo(p.tx, p.ty);
      }
      ctx.strokeStyle = "rgba(79,209,188,0.55)";
      ctx.lineWidth = 1.6;
      ctx.stroke();
    }
    for (const p of pts) {
      const k = ease(Math.max(0, Math.min(1, (time - p.delay) / 1.3)));
      let x = p.sx + (p.tx - p.sx) * k;
      let y = p.sy + (p.ty - p.sy) * k + Math.sin(time * 0.8 + p.phase) * 2 * k;
      const dx = x - mouse.x, dy = y - mouse.y, d = Math.hypot(dx, dy);
      if (d < 90) { const f = (1 - d / 90) * 18; x += (dx / (d || 1)) * f; y += (dy / (d || 1)) * f; }
      const corrected = p.flagged ? Math.max(0, Math.min(1, (time - p.delay - 1.1) / 0.5)) : 1;
      const col = p.flagged ? mix(amber, teal, corrected) : teal;
      const alpha = p.flagged ? 0.95 : 0.35 + 0.4 * k;
      ctx.beginPath();
      ctx.arc(x, y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${col.join(",")},${alpha})`;
      ctx.fill();
      if (p.flagged && corrected < 1) {
        ctx.beginPath(); ctx.arc(x, y, p.r + 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(232,176,79,${0.5 * (1 - corrected)})`; ctx.lineWidth = 1; ctx.stroke();
      }
    }
  }
  function loop(ts) {
    if (start === null) start = ts;
    draw((ts - start) / 1000);
    if (!document.hidden) requestAnimationFrame(loop); else setTimeout(() => requestAnimationFrame(loop), 300);
  }
  let lastW = canvas.clientWidth;
  window.addEventListener("resize", () => {
    if (Math.abs(canvas.clientWidth - lastW) < 40) return;   // ignore mobile URL-bar resizes
    lastW = canvas.clientWidth; resize(); start = null;
  });
  canvas.parentElement.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
  });
  canvas.parentElement.addEventListener("pointerleave", () => (mouse = { x: -999, y: -999 }));
  resize();
  if (!reduce) requestAnimationFrame(loop);
}
