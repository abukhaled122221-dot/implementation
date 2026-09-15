/**
 * Thiqa Node.js Server
 * الدور: خدمة الواجهة الأمامية (Presentation Layer) + بوابة (Gateway) لخدمة الوكلاء بايثون.
 * لاحقاً: يُضاف هنا Auth (User/Admin) وقاعدة البيانات (حسب ERD في التقرير - Chapter 3.6).
 */

const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const AGENTS_SERVICE_URL = process.env.AGENTS_SERVICE_URL || "http://127.0.0.1:8000";

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// نقطة الاتصال بين الواجهة وخدمة الوكلاء (Agent 1 -> 2 -> 3)
app.post("/api/recommend", async (req, res) => {
  try {
    const response = await fetch(`${AGENTS_SERVICE_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    // TODO: هنا لاحقاً نسجل الطلب والتوصية بقاعدة البيانات (جدول Recommendations/Explanations)
    return res.json(data);
  } catch (err) {
    console.error("Agents service error:", err.message);
    return res.status(502).json({
      error: "تعذر الاتصال بخدمة الوكلاء (Python). تأكد أنها تعمل على المنفذ 8000.",
    });
  }
});

app.get("/api/health", (req, res) => {
  res.json({ status: "ok", service: "thiqa-node-server" });
});

app.listen(PORT, () => {
  console.log(`✅ Thiqa server running: http://localhost:${PORT}`);
});
