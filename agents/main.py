"""
خدمة الوكلاء الذكية (Python / FastAPI)
تشكل الطبقة 2 من معمارية Thiqa: توجد فيها الوكلاء الثلاثة يعملون كخط أنابيب واحد
(Agent1 -> Agent2 -> Agent3) خلف endpoint واحد: POST /recommend

للتشغيل:
    pip install fastapi uvicorn --break-system-packages
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent1_receiver import DataReceiverAgent
from agent2_recommender import RecommendationAgent
from agent3_explainer import ExplainerAgent

app = FastAPI(title="Thiqa Agents Service")

# يسمح لسيرفر Node.js (على بورت مختلف) بالاتصال بهذه الخدمة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent1 = DataReceiverAgent()
agent2 = RecommendationAgent()
agent3 = ExplainerAgent()


class CustomerRequest(BaseModel):
    driver_age: int
    vehicle_value: float
    coverage_type: str  # "TPL" or "Comprehensive"
    purpose_of_use: str | None = "شخصي"
    priority: str | None = "Balanced"  # Budget | Service | Digital | Balanced


@app.get("/health")
def health():
    return {"status": "ok", "service": "thiqa-agents"}


@app.post("/recommend")
def recommend(payload: CustomerRequest):
    try:
        customer_data = payload.model_dump()

        # Agent 1: استلام البيانات وجلب العروض
        step1 = agent1.run(customer_data)

        # Agent 2: التقييم والترتيب واختيار الأفضل (حسب أولوية العميل)
        step2 = agent2.run(
            step1["unified_quote_set"],
            step1["customer_profile"],
            priority=customer_data.get("priority", "Balanced"),
        )

        # Agent 3: توليد التفسير بلغة بسيطة
        step3 = agent3.run(step2["selected"], step2["ranked"])

        return {
            "recommended_package": step2["selected"],
            "all_offers_ranked": step2["ranked"],
            "explanation": step3,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
