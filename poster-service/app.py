from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/post")
async def mock_post(req: Request):
    data = await req.json()
    print("📣 MOCK POST:", data)
    return {"status": "ok", "msg": "Simulated post"}

