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
createat_list = collections.deque(maxlen=288)

HISTORY_PATH = Path("/var/www/html/history_seis.jsonl")
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
                createat_list.append(str(row["t"]))
                temperature_list.append(float(row["temperature"]))
                humidity_list.append(float(row["humidity"]))
                pressure_list.append(float(row["pressure"]))
            except Exception:
                continue
    except Exception as e:
        print(
            f"{datetime.datetime.now().strftime('[%H:%M:%S]')} History load error: {e}"
        )


def append_history(weather_data):
    """追加一条数据到历史文件，并裁剪到最多24小时(288条)"""
    row = {
        "t": weather_data[3],
        "temperature": weather_data[0],
        "humidity": weather_data[1],
        "pressure": weather_data[2],
    }
    try:
        # 1) 先追加一行
        with HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 2) 再裁剪到最多 MAX_POINTS 行（读尾部再原子替换）
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
        with open("/var/www/html/data_seis.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        temperature = _to_float(data["temperature"], "temperature")
        humidity = _to_float(data["humidity"], "humidity")
        pressure = _to_float(data["pressure"], "pressure")
        # 避免跨天 x 轴重复：尽量用完整时间
        ca = str(data.get("create_at", "")).strip()
        if len(ca) >= 19 and ca[4] == "-" and ca[7] == "-" and ca[10] in (" ", "T"):
            create_at = ca[:19].replace("T", " ")
        else:
            create_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
        return None
    return (
        temperature,
        humidity,
        pressure,
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
                temperature_list.append(weather_data[0])
                humidity_list.append(weather_data[1])
                pressure_list.append(weather_data[2])
                createat_list.append(weather_data[3])
                plot(
                    list(createat_list),
                    list(temperature_list),
                    "温度 (℃)",
                    "测站环境温度",
                    "/var/www/html/temperature_seis.html",
                )
                plot(
                    list(createat_list),
                    list(humidity_list),
                    "湿度 (%RH)",
                    "测站环境湿度",
                    "/var/www/html/humidity_seis.html",
                )
                plot(
                    list(createat_list),
                    list(pressure_list),
                    "大气压 (hPa)",
                    "测站环境大气压",
                    "/var/www/html/pressure_seis.html",
                )
                time.sleep(300)
            else:
                time.sleep(5)
        except Exception as e:
            print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
            time.sleep(1)
            continue
