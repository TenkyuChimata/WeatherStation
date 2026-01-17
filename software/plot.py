# -*- coding: utf-8 -*-
import os
import time
import json
import datetime
import collections
from pathlib import Path
from pyecharts import options as opts
from pyecharts.charts import Line, Page

temperature_list = collections.deque(maxlen=288)
humidity_list = collections.deque(maxlen=288)
pressure_list = collections.deque(maxlen=288)
pm1p0_list = collections.deque(maxlen=288)
pm2p5_list = collections.deque(maxlen=288)
pm4_list = collections.deque(maxlen=288)
pm10_list = collections.deque(maxlen=288)
createat_list = collections.deque(maxlen=288)
radiation_list = collections.deque(maxlen=288)
radiation_avg_list = collections.deque(maxlen=288)

HISTORY_PATH = Path("/var/www/html/history.jsonl")
MAX_POINTS = 288  # 24h * (60/5) = 288
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)


def _to_float(v, name="value"):
    try:
        return float(v)
    except Exception:
        raise ValueError(f"Invalid {name}={v!r}")


def load_history():
    """启动时恢复最近24小时数据到内存deque"""
    if not HISTORY_PATH.exists():
        return
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-MAX_POINTS:]
        for line in lines:
            try:
                row = json.loads(line)
                # 兼容字段名：t 为时间
                createat_list.append(str(row["t"]))
                temperature_list.append(float(row["temperature"]))
                humidity_list.append(float(row["humidity"]))
                pressure_list.append(float(row["pressure"]))
                pm1p0_list.append(float(row["pm1.0"]))
                pm2p5_list.append(float(row["pm2.5"]))
                pm4_list.append(float(row["pm4.0"]))
                pm10_list.append(float(row["pm10"]))
                radiation_list.append(float(row["usv"]))
                radiation_avg_list.append(float(row["usv_avg"]))
            except Exception:
                # 跳过坏行
                continue
    except Exception as e:
        print(
            f"{datetime.datetime.now().strftime('[%H:%M:%S]')} History load error: {e}"
        )


def append_history(weather_data):
    """追加一条数据到历史文件，并裁剪到最多24小时(288条)"""
    row = {
        "t": weather_data[9],
        "temperature": weather_data[0],
        "humidity": weather_data[1],
        "pressure": weather_data[2],
        "pm1.0": weather_data[3],
        "pm2.5": weather_data[4],
        "pm4.0": weather_data[5],
        "pm10": weather_data[6],
        "usv": weather_data[7],
        "usv_avg": weather_data[8],
    }
    try:
        # 1) 先追加一行
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 2) 再裁剪到最多 MAX_POINTS 行（最小实现：读尾部再原子替换）
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_POINTS:
            lines = lines[-MAX_POINTS:]
            tmp = str(HISTORY_PATH) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, HISTORY_PATH)
    except Exception as e:
        print(
            f"{datetime.datetime.now().strftime('[%H:%M:%S]')} History append error: {e}"
        )


def get_data():
    try:
        with open("/var/www/html/data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        temperature = _to_float(data["temperature"], "temperature")
        humidity = _to_float(data["humidity"], "humidity")
        pressure = _to_float(data["pressure"], "pressure")
        pm1p0 = _to_float(data["pm1.0"], "pm1.0")
        pm2p5 = _to_float(data["pm2.5"], "pm2.5")
        pm4 = _to_float(data["pm4.0"], "pm4.0")
        pm10 = _to_float(data["pm10"], "pm10")
        radiation = _to_float(data["usv"], "usv")
        radiation_avg = _to_float(data["usv_avg"], "usv_avg")
        # 避免跨天 x 轴重复：尽量用完整时间
        ca = str(data.get("create_at", "")).strip()
        if len(ca) >= 19 and ca[4] == "-" and ca[7] == "-" and ca[10] in (" ", "T"):
            # 形如 2026-01-18 12:34:56 / 2026-01-18T12:34:56
            create_at = ca[:19].replace("T", " ")
        else:
            # 兜底：用本地当前时间
            create_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
        return None
    return (
        temperature,
        humidity,
        pressure,
        pm1p0,
        pm2p5,
        pm4,
        pm10,
        radiation,
        radiation_avg,
        create_at,
    )


def plot(x, y, y_name, plot_name, html_name):
    line = (
        Line(init_opts=opts.InitOpts(width="100%", height="815px"))
        .add_xaxis(x)
        .add_yaxis(y_name, y, is_smooth=True, label_opts=opts.LabelOpts(is_show=False))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=plot_name),
            xaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(rotate=90, interval=0, is_show=False)
            ),
            yaxis_opts=opts.AxisOpts(is_scale=True),
        )
    )
    page = Page(layout=Page.SimplePageLayout, page_title=plot_name)
    page.add(line)
    # 原子写入：避免 Nginx/浏览器读到半截文件
    tmp = html_name + ".tmp"
    try:
        page.render(tmp)
        os.replace(tmp, html_name)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


if __name__ == "__main__":

    load_history()

    while True:
        try:
            weather_data = get_data()
            if weather_data is not None:
                append_history(weather_data)
                temperature_list.append(weather_data[0])
                humidity_list.append(weather_data[1])
                pressure_list.append(weather_data[2])
                pm1p0_list.append(weather_data[3])
                pm2p5_list.append(weather_data[4])
                pm4_list.append(weather_data[5])
                pm10_list.append(weather_data[6])
                radiation_list.append(weather_data[7])
                radiation_avg_list.append(weather_data[8])
                createat_list.append(weather_data[9])
                plot(
                    list(createat_list),
                    list(temperature_list),
                    "温度 (℃)",
                    "温度",
                    "/var/www/html/temperature.html",
                )
                plot(
                    list(createat_list),
                    list(humidity_list),
                    "湿度 (%RH)",
                    "湿度",
                    "/var/www/html/humidity.html",
                )
                plot(
                    list(createat_list),
                    list(pressure_list),
                    "大气压 (hPa)",
                    "大气压",
                    "/var/www/html/pressure.html",
                )
                plot(
                    list(createat_list),
                    list(radiation_list),
                    "电离辐射 (μSv/h)",
                    "电离辐射",
                    "/var/www/html/radiation.html",
                )
                plot(
                    list(createat_list),
                    list(radiation_avg_list),
                    "电离辐射 (μSv/h)",
                    "电离辐射(小时均值)",
                    "/var/www/html/radiation_avg.html",
                )
                plot(
                    list(createat_list),
                    list(pm1p0_list),
                    "PM1.0 (μg/m³)",
                    "PM1.0",
                    "/var/www/html/pm1.0.html",
                )
                plot(
                    list(createat_list),
                    list(pm2p5_list),
                    "PM2.5 (μg/m³)",
                    "PM2.5",
                    "/var/www/html/pm2.5.html",
                )
                plot(
                    list(createat_list),
                    list(pm4_list),
                    "PM4 (μg/m³)",
                    "PM4",
                    "/var/www/html/pm4.html",
                )
                plot(
                    list(createat_list),
                    list(pm10_list),
                    "PM10 (μg/m³)",
                    "PM10",
                    "/var/www/html/pm10.html",
                )
                time.sleep(300)
            else:
                time.sleep(5)
        except Exception as e:
            print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
            time.sleep(1)
            continue
