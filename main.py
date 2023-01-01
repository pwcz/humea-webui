import json
from typing import Optional

import tinytuya
from fastapi import FastAPI
from pydantic import BaseModel

device: tinytuya.OutletDevice = None
app = FastAPI()

HUMIDITY_TABLE = {"0": "CO"}
for i, x in enumerate(range(40, 80, 5), start=1):
    HUMIDITY_TABLE[str(i)] = str(x)


class DpsValues(BaseModel):
    power: Optional[bool] = None
    sleep_mode: Optional[bool] = None


@app.get("/status")
def handle_get_status():
    data = device.status()
    return {"power": data["dps"]["10"],
            "water_level": "ok" if data["dps"]["101"] == '1' else "too low",
            "night_level": data["dps"]["102"],
            "sleep_mode": data["dps"]["103"],
            "auto_mode": data["dps"]["104"],
            "humidity_settings": HUMIDITY_TABLE[data["dps"]["105"]],
            "moisture_output_level": HUMIDITY_TABLE[data["dps"]["106"]],
            "filter_status": "ok" if data["dps"]["107"] == "0" else "error",
            "timer": data["dps"]["108"],
            "humidity": data["dps"]["109"]
            }


@app.post("/dps")
def handle_post_state(item: DpsValues):
    if item.power is not None:
        device.set_value(10, item.power)

    if item.sleep_mode is not None:
        device.set_value(103, item.sleep_mode)

    return {"status": "ok"}


@app.on_event("shutdown")
def shutdown_event():
    device.close()


@app.on_event("startup")
def startup_event():
    global device
    with open("api_cfg.json") as file:
        cfg = json.loads(file.read())
    device = tinytuya.OutletDevice(cfg["dev_id"], cfg["address"], cfg["local_key"])
    device.set_version(3.3)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
