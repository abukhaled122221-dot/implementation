/**
 * صفحة "توصياتي السابقة": قائمة طلبات العميل المحفوظة + تفاصيل كل طلب.
 * البيانات من GET /api/history و GET /api/history/:id (العميل يرى طلباته فقط).
 */
(() => {
  const PAGE_SIZE = 10;
  const esc = TH.escapeHtml;
  const list = document.getElementById("history-list");
  const pager = document.getElementById("history-pagination");
  const modal = document.getElementById("detail-modal");
  let page = 1;

  document.addEventListener("DOMContentLoaded", async () => {
    const user = await TH.renderAuthNav();
    if (!user) {
      TH.goToLogin("/history.html");
      return;
    }
    loadPage(1);
  });

  // ---------------------------------------------------------------- القائمة
  function skeleton() {
    return Array.from({ length: 3 })
      .map(
        () =>
          `<div class="h-24 rounded-2xl bg-white border border-slate-100 animate-pulse"></div>`,
      )
      .join("");
  }

  async function loadPage(target) {
    page = target;
    list.innerHTML = skeleton();
    pager.innerHTML = "";
    try {
      const data = await TH.api(
        `/api/history?page=${page}&pageSize=${PAGE_SIZE}`,
        {
          onUnauthorized: () => TH.goToLogin("/history.html"),
        },
      );
      const items = data.items || data.history || [];
      renderList(items);
      renderPager(items.length, data.total);
    } catch (error) {
      list.innerHTML = `<div class="p-6 rounded-2xl bg-red-50 text-red-700 font-bold">${esc(error.message)}</div>`;
    }
  }

  function renderList(items) {
    if (!items.length) {
      list.innerHTML = `
        <div class="bg-white rounded-3xl border border-slate-100 p-12 text-center">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center text-2xl">
            <i class="fa-solid fa-folder-open"></i>
          </div>
          <h2 class="text-lg font-black text-navy-800">لا توجد توصيات بعد</h2>
          <p class="text-sm text-slate-500 mt-1 mb-5">ابدأ أول طلب لمقارنة عروض التأمين لسيارتك.</p>
          <a href="/#recommendation" class="inline-block bg-brand-600 hover:bg-brand-700 text-white font-bold px-5 py-3 rounded-xl text-sm">
            طلب توصية
          </a>
        </div>`;
      return;
    }

    list.innerHTML = items.map(renderItem).join("");
    list
      .querySelectorAll("[data-request]")
      .forEach((button) =>
        button.addEventListener("click", () =>
          openDetail(button.dataset.request),
        ),
      );
  }

  function renderItem(item) {
    const ok = item.Status === "success";
    const selected = ok
      ? `<b class="text-navy-800">${esc(item.ProviderName || "—")}</b>
         <span class="text-slate-500">${esc(item.PlanName || "")}</span>`
      : `<span class="text-red-600">${esc(item.ErrorMessage || "لم تكتمل التوصية")}</span>`;

    return `
      <article class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div class="space-y-1.5 min-w-0">
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <span class="font-black text-slate-400">#${esc(item.RequestId)}</span>
            ${TH.statusBadge(ok, "تمت التوصية", "فشل الطلب")}
            <span class="px-2 py-1 rounded-lg bg-slate-100 text-slate-600 font-bold">${esc(TH.coverageLabel(item.CoverageType))}</span>
            <span class="px-2 py-1 rounded-lg bg-slate-100 text-slate-600 font-bold">${esc(TH.priorityLabel(item.Priority))}</span>
          </div>
          <p class="text-sm truncate">${selected}</p>
          <p class="text-xs text-slate-400"><i class="fa-regular fa-clock ml-1"></i>${esc(TH.formatDate(item.Timestamp))}</p>
        </div>
        <div class="flex items-center gap-4 shrink-0">
          ${
            ok
              ? `<div class="text-left">
                 <div class="font-black text-lg">${TH.formatSAR(item.Premium)}</div>
                 <div class="text-xs text-slate-500">التوافق ${TH.formatScore(item.SuitabilityScore)}</div>
               </div>`
              : ""
          }
          <button type="button" data-request="${Number(item.RequestId)}"
            class="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold">
            التفاصيل
          </button>
        </div>
      </article>`;
  }

  function renderPager(count, total) {
    const totalPages = total ? Math.max(1, Math.ceil(total / PAGE_SIZE)) : null;
    const hasNext = totalPages ? page < totalPages : count === PAGE_SIZE;
    if (page === 1 && !hasNext) return;

    const button = (label, target, enabled) =>
      `<button type="button" ${enabled ? `data-page="${target}"` : "disabled"}
         class="px-4 py-2 rounded-xl font-bold ${enabled ? "bg-white border border-slate-200 hover:bg-slate-50" : "bg-slate-100 text-slate-400"}">
         ${label}</button>`;

    pager.innerHTML = `
      ${button('<i class="fa-solid fa-chevron-right ml-1"></i>السابق', page - 1, page > 1)}
      <span class="text-slate-500">الصفحة ${page}${totalPages ? ` من ${totalPages}` : ""}</span>
      ${button('التالي<i class="fa-solid fa-chevron-left mr-1"></i>', page + 1, hasNext)}`;
    pager
      .querySelectorAll("[data-page]")
      .forEach((el) =>
        el.addEventListener("click", () => loadPage(Number(el.dataset.page))),
      );
  }

  // ---------------------------------------------------------------- التفاصيل
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-close-modal]"))
      closeDetail();
  });
  document.addEventListener(
    "keydown",
    (event) => event.key === "Escape" && closeDetail(),
  );

  function closeDetail() {
    modal.classList.add("hidden");
  }

  async function openDetail(requestId) {
    document.getElementById("detail-title").textContent =
      `تفاصيل الطلب #${requestId}`;
    const body = document.getElementById("detail-body");
    body.innerHTML = `<div class="h-40 rounded-2xl bg-slate-100 animate-pulse"></div>`;
    modal.classList.remove("hidden");
    try {
      const detail = await TH.api(
        `/api/history/${encodeURIComponent(requestId)}`,
      );
      body.innerHTML = TH.renderRequestDetail(detail);
    } catch (error) {
      body.innerHTML = `<p class="text-red-600 font-bold">${esc(error.message)}</p>`;
    }
  }
})();
