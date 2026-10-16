/* Mini charts on the home page, drawn from the same JSON the case studies use */
(() => {
  const { c, fmt, compact, load, whenVisible } = window.Viz;
  const base = "assets/data/";
  const axisPct = { ticks: { callback: (v) => v + "%" } };

  whenVisible(document.getElementById("mini-proc"), async () => {
    const d = await load(base + "procurement.json");
    const col = { "OEM": c.blue, "Authorised distributor": c.teal, "Aftermarket": c.amber };
    const s = d.suppliers;
    new Chart(document.getElementById("mini-proc"), {
      type: "bar",
      data: { labels: s.map((r) => r.supplier_name), datasets: [{ data: s.map((r) => r.score), backgroundColor: s.map((r) => col[r.supplier_type]), barThickness: 10 }] },
      options: {
        indexAxis: "y",
        scales: { x: { min: 0, max: 100, grid: { color: c.grid } }, y: { grid: { display: false }, ticks: { color: "#b0c0cb", font: { size: 10 } } } },
        plugins: {
          legend: { display: true, position: "bottom", labels: { color: "#b0c0cb", boxWidth: 10, boxHeight: 10, padding: 12,
            generateLabels: () => Object.entries(col).map(([t, cc]) => ({ text: t, fillStyle: cc, strokeStyle: cc, lineWidth: 0, fontColor: "#b0c0cb" })) } },
          tooltip: { callbacks: { label: (i) => ` score ${i.raw}`, afterLabel: (i) => ` OTIF ${s[i.dataIndex].otif_pct}% · rejects ${s[i.dataIndex].reject_pct}%` } },
        },
      },
    });
  });

  whenVisible(document.getElementById("mini-hotel"), async () => {
    const d = await load(base + "hotel-esg.json");
    new Chart(document.getElementById("mini-hotel"), {
      type: "bar",
      data: {
        labels: d.recall.map((r) => r.label),
        datasets: [
          { label: "Caught", data: d.recall.map((r) => r.caught), backgroundColor: c.teal, barThickness: 14 },
          { label: "Missed", data: d.recall.map((r) => r.total - r.caught), backgroundColor: c.amber, barThickness: 14 },
        ],
      },
      options: {
        indexAxis: "y",
        scales: { x: { stacked: true, grid: { color: c.grid } }, y: { stacked: true, grid: { display: false }, ticks: { color: "#b0c0cb" } } },
        plugins: { tooltip: { callbacks: { footer: (items) => {
          const r = d.recall[items[0].dataIndex];
          return `${r.caught} of ${r.total} caught`;
        } } } },
      },
    });
  });

  whenVisible(document.getElementById("mini-ecom"), async () => {
    const d = await load(base + "ecommerce.json");
    new Chart(document.getElementById("mini-ecom"), {
      type: "line",
      data: { labels: d.monthly.months, datasets: [{ label: "GMV", data: d.monthly.gmv, borderColor: c.teal, tension: 0.35, pointHoverBackgroundColor: c.teal }] },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { grid: { color: c.grid }, ticks: { callback: (v) => compact(v) } } },
        plugins: { tooltip: { callbacks: { label: (i) => ` GMV R$ ${fmt(i.raw)}` } } },
      },
    });
  });

  whenVisible(document.getElementById("mini-delivery"), async () => {
    const d = await load(base + "delivery.json");
    new Chart(document.getElementById("mini-delivery"), {
      type: "bar",
      data: {
        labels: d.impact.map((r) => r.late_bucket.replace(" late", "")),
        datasets: [{ label: "1–2 star share", data: d.impact.map((r) => r.bad_review_pct),
          backgroundColor: d.impact.map((r, i) => (i === 0 ? c.teal : c.amber)), maxBarThickness: 44 }],
      },
      options: {
        scales: { x: { grid: { display: false } }, y: { ...axisPct, grid: { color: c.grid }, max: 100 } },
        plugins: { tooltip: { callbacks: { label: (i) => ` ${i.raw}% of reviews are 1–2 stars`,
          afterLabel: (i) => ` ${fmt(d.impact[i.dataIndex].orders)} orders` } } },
      },
    });
  });

  whenVisible(document.getElementById("mini-equip"), async () => {
    const d = await load(base + "equipment.json");
    const sites = d.mttr.site.map((s) => s.split(" - ")[1]);
    new Chart(document.getElementById("mini-equip"), {
      type: "bar",
      data: {
        labels: sites,
        datasets: [
          { label: "Repair", data: d.mttr.repair_h, backgroundColor: c.teal, maxBarThickness: 44 },
          { label: "Waiting for parts", data: d.mttr.waiting_parts_h, backgroundColor: c.amber, maxBarThickness: 44 },
          { label: "Waiting for mechanic", data: d.mttr.waiting_mechanic_h, backgroundColor: c.blue, maxBarThickness: 44 },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { color: c.grid }, ticks: { callback: (v) => v + " h" } } },
        plugins: {
          legend: { display: true, position: "bottom", labels: { usePointStyle: true, pointStyle: "rectRounded", boxWidth: 10, boxHeight: 10, color: "#b0c0cb", padding: 14 } },
          tooltip: { callbacks: { label: (i) => ` ${i.dataset.label}: ${i.raw} h` } },
        },
      },
    });
  });
})();
