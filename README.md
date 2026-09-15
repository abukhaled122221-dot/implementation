# THIQA — منصة التوصية الذكية بتأمين السيارات

هذا الهيكل هو نقطة انطلاق فيز 2 (التنفيذ)، مبني على تصميم فيز 1 (راجع `docs/THIQA_Car_Insurance_Report.pdf`، الفصل 3).

## البنية المعمارية (Three-Layer Architecture)

```
المتصفح (الواجهة - server/public/index.html)
        │  fetch('/api/recommend')
        ▼
Node.js / Express  (server/)         ← Layer 1 + Gateway
        │  POST http://localhost:8000/recommend
        ▼
Python / FastAPI  (agents/)          ← Layer 2: الوكلاء الثلاثة
   Agent 1 (الاستلام والجلب) → Agent 2 (التوصية) → Agent 3 (الشرح)
        │
        ▼
Mock Insurers (agents/mock_insurers.py)  ← Layer 3 (محاكاة APIs شركات التأمين)
```

- **Node.js**: يخدم الواجهة، ولاحقاً سيتولى تسجيل الدخول (User/Admin) وقاعدة البيانات (حسب ERD في التقرير، القسم 3.6).
- **Python (FastAPI)**: فيه منطق الوكلاء الثلاثة فعلياً (تحقق، تسجيل نقاط، شرح) — قابل للتوسعة لاحقاً بنماذج AI حقيقية.
- **Mock Insurers**: بيانات وهمية تحاكي Tawuniya / Takaful Al-Rajhi / Medgulf / ACIG، يمكن استبدالها لاحقاً بطلبات API حقيقية بدون تغيير بقية الكود.

## التشغيل محلياً

### 1) تشغيل خدمة الوكلاء (Python)
```bash
cd agents
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) تشغيل السيرفر الرئيسي (Node.js) — في نافذة طرفية ثانية
```bash
cd server
npm install
npm start
```

### 3) افتح المتصفح
```
http://localhost:3000
```

## الخطوات القادمة المقترحة لفيز 2
- [ ] إضافة قاعدة بيانات (SQLite/Postgres) حسب ERD في التقرير (Users, Customer_Profiles, Vehicles, Quote_Requests, Recommendations, Explanations)
- [ ] تسجيل دخول حقيقي للعميل والمدير (Auth) وفصل مسار الأدمن
- [ ] لوحة تحكم Admin لإدارة شركات التأمين وإعدادات الـ API
- [ ] إضافة حقل "قيمة السيارة" و"الرقم التسلسلي" فعلياً للفورم وربطها بالحساب
- [ ] استبدال Mock APIs بواجهات حقيقية إذا توفر تعاون مع شركات تأمين
- [ ] تسجيل كل توصية وتفسير في قاعدة البيانات (Logging) للتدقيق لاحقاً

## هيكلة المجلدات
```
thiqa/
├── agents/                  # خدمة بايثون (الوكلاء الثلاثة)
│   ├── main.py              # FastAPI app + orchestration
│   ├── agent1_receiver.py
│   ├── agent2_recommender.py
│   ├── agent3_explainer.py
│   ├── mock_insurers.py
│   └── requirements.txt
├── server/                  # سيرفر Node.js
│   ├── server.js
│   ├── package.json
│   └── public/
│       └── index.html       # الواجهة (معدّلة لتتصل بالباك اند الحقيقي)
├── docs/                    # التقرير والعروض التقديمية من فيز 1
└── README.md
```
