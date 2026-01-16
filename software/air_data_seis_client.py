# -*- coding: utf-8 -*-
import json
import time
import requests
import datetime

while True:
    try:
        esp8266_data = requests.get("http://192.168.0.11/data_seis.json", timeout=10).json()
        data = {
            "temperature": esp8266_data["temperature"],
            "humidity": esp8266_data["humidity"],
            "pressure": esp8266_data["pressure"],
            "create_at": esp8266_data["create_at"],
        }
        with open("/var/www/html/data_seis.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
        time.sleep(60)
    except Exception as e:
        print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
        time.sleep(1)
        continue
