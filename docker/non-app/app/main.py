import os
import time

from fastapi import FastAPI

app = FastAPI(title="pid1-resource-demo")

START_TIME = time.time()

@app.get("/")
async def root():
    return {
        "message": "Home",
        "PID" : os.getpid(),
        "Uptime" : round(time.time() - START_TIME)
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/cpu-test")
async def cpu_test(sec : int = 3):
    end = time.time() + sec
    x = 0
    while time.time() < end:
        x += 1
    return {"count": x, "duration": sec}

@app.get("/memory-test")
async def memory_test(size_mb : int = 100):
    block = bytearray(size_mb * 1024 * 1024)
    return {"allocated_mb": size_mb, "size_bytes": len(block)}