/**
 * عرض تفاصيل طلب توصية محفوظ (بيانات الطلب + سبب التوصية + كل العروض المقارنة).
 * مشترك بين صفحة "توصياتي السابقة" وسجل التوصيات في لوحة الأدمن.
 * يتطلب تحميل common.js قبله.
 */
(() => {
  const esc = TH.escapeHtml;

  function renderRequestDetail(detail) {
    const request = detail.request || {};
    const payload = TH.parseJson(request.RequestPayload, {}) || {};
    const quotes = detail.quotes || [];
    const explanation = detail.explanation;
    const selectedId = detail.recommendation?.SelectedQuoteId;

    const info = [
      ["التاريخ", TH.formatDate(request.Timestamp)],
      [
        "نوع التغطية",
        TH.coverageLabel(request.CoverageType || payload.coverage_type),
      ],
      ["الأولوية", TH.priorityLabel(request.Priority || payload.priority)],
      ["قيمة المركبة", TH.formatSAR(payload.vehicle_value)],
      ["سنة الصنع", payload.manufacture_year || "—"],
      [
        "الإضافات المطلوبة",
        (payload.requested_add_ons || []).map(TH.addonLabel).join("، ") ||
          "لا يوجد",
      ],
    ]
      .map(
        ([label, value]) => `
        <div class="bg-slate-50 rounded-xl p-3">
          <div class="text-xs text-slate-400">${esc(label)}</div>
          <div class="text-sm font-bold">${esc(value)}</div>
        </div>`,
      )
      .join("");

    const explanationHtml = explanation
      ? `<section class="rounded-2xl border border-brand-100 bg-brand-50/50 p-5 space-y-2">
           <h3 class="font-black text-brand-700"><i class="fa-solid fa-lightbulb ml-1"></i>سبب التوصية</h3>
           <p class="text-sm leading-relaxed">${esc(explanation.MainReasons)}</p>
           ${
             explanation.ComparisonText
               ? `<p class="text-xs text-slate-500 leading-relaxed">${esc(explanation.ComparisonText)}</p>`
               : ""
           }
         </section>`
      : request.Status === "failed"
        ? `<p class="p-4 rounded-2xl bg-red-50 text-red-700 text-sm font-bold">
             ${esc(request.ErrorMessage || "لم تكتمل التوصية")}</p>`
        : "";

    const rows = quotes
      .map((quote) => {
        const isSelected = quote.QuoteId === selectedId;
        const addOns = TH.parseJson(quote.AddOns, []) || [];
        return `
          <tr class="${isSelected ? "bg-brand-50" : ""} border-t border-slate-100">
            <td class="p-2 text-center font-black text-slate-400">${esc(quote.Rank ?? "")}</td>
            <td class="p-2">
              <div class="font-bold">${esc(quote.ProviderName || quote.ProviderId)}
                ${isSelected ? '<i class="fa-solid fa-crown text-brand-600 mr-1"></i>' : ""}</div>
              <div class="text-xs text-slate-500">${esc(quote.PlanName || "")}</div>
            </td>
            <td class="p-2 font-bold whitespace-nowrap">${TH.formatSAR(quote.Premium)}</td>
            <td class="p-2 whitespace-nowrap">${TH.formatSAR(quote.Deductible)}</td>
            <td class="p-2 text-xs">${esc(addOns.map(TH.addonLabel).join("، ") || "—")}</td>
            <td class="p-2 font-bold">${TH.formatScore(quote.SuitabilityScore)}</td>
          </tr>`;
      })
      .join("");

    return `
      <div class="space-y-6">
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">${info}</div>
        ${explanationHtml}
        ${
          quotes.length
            ? `<section>
               <h3 class="font-black text-navy-800 mb-3">العروض التي تمت مقارنتها (${quotes.length})</h3>
               <div class="overflow-x-auto rounded-2xl border border-slate-100">
                 <table class="w-full text-sm text-right">
                   <thead class="bg-slate-50 text-xs text-slate-500">
                     <tr><th class="p-2">#</th><th class="p-2">الشركة / الباقة</th><th class="p-2">القسط</th>
                         <th class="p-2">التحمل</th><th class="p-2">الإضافات</th><th class="p-2">التوافق</th></tr>
                   </thead>
                   <tbody>${rows}</tbody>
                 </table>
               </div>
             </section>`
            : ""
        }
      </div>`;
  }

  TH.renderRequestDetail = renderRequestDetail;
})();
