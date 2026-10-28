"""
خدمة الوكلاء الذكية (Python / FastAPI)
تشكل الطبقة 2 من معمارية Thiqa: الوكلاء الثلاثة يعملون كخط أنابيب واحد
(Agent1 -> Agent2 -> Agent3) خلف endpoint واحد: POST /recommend
"""

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import time
import httpx
from insurers_config import load_insurers_from_db

from agent1_receiver import DataReceiverAgent, InvalidCustomerData, NoOffersAvailable
from agent2_recommender import RecommendationAgentV2
from agent3_explainer import ExplainerAgent
from orchestrator import NoEligibleOffers, coordinate_recommendation

app = FastAPI(title="Thiqa Agents Service")

# يسمح لسيرفر Node.js (على بورت مختلف) بالاتصال بهذه الخدمة
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("AGENTS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent1 = DataReceiverAgent()
agent2 = RecommendationAgentV2()
agent3 = ExplainerAgent()


def _error(status: int, message: str, **extra):
    return JSONResponse(status_code=status, content={"error": message, **extra})


@app.get("/providers")
def providers():
    """Expose provider connection metadata without returning API credentials."""
    return [
        {
            "provider_id": insurer["provider_id"],
            "name": insurer["name"],
            "adapter": insurer["adapter"],
            "url": insurer["base_url"].rstrip("/") + insurer["path"],
            "auth_scheme": insurer["auth_scheme"],
            "timeout": insurer["timeout"],
            "active": insurer.get("active", True),
            "source": insurer.get("_source", "defaults"),
        }
        for insurer in load_insurers_from_db(include_inactive=True)
    ]


@app.post("/providers/test")
async def provider_test(payload: dict = Body(...)):
    """Probe DB-loaded insurer settings without saving a quote or customer data."""
    provider_id = payload.get("provider_id") if isinstance(payload, dict) else None
    insurer = next(
        (
            item
            for item in load_insurers_from_db(include_inactive=True)
            if item["provider_id"] == provider_id
        ),
        None,
    )
    if insurer is None:
        return JSONResponse(status_code=404, content={"error": "provider not found"})
    sample = {"national_id": "1098765432", "birth_date": "1990-01-01", "driver_age": 36, "vehicle_serial": "123456789", "manufacture_year": 2021, "vehicle_value": 50000, "vehicle_age": 5, "purpose_of_use": "personal", "annual_mileage": "medium", "coverage_type": "TPL", "priority": "Balanced", "requested_add_ons": [], "city": "riyadh", "gender": "male", "has_accidents": "no", "cars_count": "single"}
    async with httpx.AsyncClient() as client:
        result = await agent1._query_insurer(client, insurer, sample)
    return {"provider_id": provider_id, "ok": result.ok, "error_type": result.error_type, "error_message": result.error_message, "latency_ms": result.latency_ms, "offers_count": len(result.quotes)}


@app.get("/health")
def health():
    return {"status": "ok", "service": "thiqa-agents"}


@app.post("/agent1/retrieve")
async def agent1_retrieve(payload: dict = Body(...)):
    """تشغيل Agent 1 وحده (للاختبار المستقل): يرجع العروض الموحدة وحالة كل شركة."""
    try:
        return await agent1.run(payload)
    except InvalidCustomerData as e:
        return _error(422, "بيانات غير صالحة", errors=e.errors)
    except NoOffersAvailable as e:
        return _error(503, str(e), provider_status=e.provider_status)


@app.post("/recommend")
async def recommend(payload: dict = Body(...)):
    try:
        # Agent 1: استلام البيانات والتحقق وجلب العروض من الشركات وتوحيدها
        step1 = await agent1.run(payload)
    except InvalidCustomerData as e:
        return _error(422, "بيانات غير صالحة: " + "، ".join(x["message"] for x in e.errors), errors=e.errors)
    except NoOffersAvailable as e:
        return _error(503, str(e), provider_status=e.provider_status)

    try:
        # Run the agent pipeline to get the recommendation
        result = coordinate_recommendation(step1, agent2, agent3)

        # الحفظ في قاعدة البيانات لا يتم هنا: سيرفر Node يحفظ الطلب والعروض والتوصية
        # والتفسير في معاملة واحدة مرتبطة بحساب العميل (server/services/recommendationStore.js).
        return result
    except NoEligibleOffers as e:
        return _error(503, str(e), provider_status=e.provider_status)