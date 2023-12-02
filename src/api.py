import os
import logging as log
import json
from typing import Optional
from datetime import datetime, time

import tinytuya
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi_utils.tasks import repeat_every
import telegram


log.basicConfig(level=log.INFO)
device: tinytuya.OutletDevice = None
app = FastAPI()

HUMIDITY_TABLE = {"0": "CO"}
for i, x in enumerate(range(40, 80, 5), start=1):
    HUMIDITY_TABLE[str(i)] = str(x)


API_TELEGRAM = os.environ['API_TELEGRAM']
CHANNEL_ID = os.environ['CHANNEL_ID']
DEVICE_ID = os.environ['DEVICE_ID']
DEVICE_ADDRESS = os.environ['DEVICE_ADDRESS']
DEVICE_LOCAL_KEY = os.environ['DEVICE_LOCAL_KEY']

telegram_bot = telegram.Bot(token=API_TELEGRAM)
notification_data = {"send": False}


class DpsValues(BaseModel):
    power: Optional[bool] = None
    sleep_mode: Optional[bool] = None


def get_device_status():
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


@app.get("/status")
def handle_get_status():
    return get_device_status()


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
@repeat_every(seconds=60, wait_first=True)
async def monitor_humidifier():
    status = get_device_status()

    # AUTO sleep mode
    current_time = datetime.now().time()
    should_sleep = (time(8, 00) >= current_time or current_time >= time(23, 30))
    if status["sleep_mode"] != should_sleep:
        log.info(f"changing sleep mode to {should_sleep}")
        device.set_value(103, should_sleep)

    # notification when no water
    if status["water_level"] != "ok" and not notification_data["send"]:
        await telegram_bot.send_message(chat_id=CHANNEL_ID, text='Fill me up!')
        notification_data["send"] = True
    elif status["water_level"] == "ok" and notification_data["send"]:
        notification_data["send"] = False


@app.on_event("startup")
def startup_event():
    global device
    device = tinytuya.OutletDevice(DEVICE_ID, DEVICE_ADDRESS, DEVICE_LOCAL_KEY)
    device.set_version(3.3)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
