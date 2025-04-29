# data_api.py (نسخة وهمية للاختبار)
import asyncio

class ApiClient:
    async def call_api_async(self, endpoint, query=None):
        print(f"[Mock API] Calling {endpoint} with query={query}")
        await asyncio.sleep(0.1)
        # يمكنك تخصيص النتائج حسب الحاجة لاحقًا
        return {
            "mock": True,
            "endpoint": endpoint,
            "query": query
        }
