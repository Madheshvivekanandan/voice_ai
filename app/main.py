import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from websocket.call_handler import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Voice AI — Audio Stream Server",
    version="0.2.0",
)

app.include_router(ws_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
