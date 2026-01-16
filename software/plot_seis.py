# -*- coding: utf-8 -*-
import time
import requests
import datetime
import collections
from pyecharts.charts import Line, Page
from pyecharts import options as opts

temperature_list = collections.deque(maxlen=288)
humidity_list = collections.deque(maxlen=288)
pressure_list = collections.deque(maxlen=288)
createat_list = collections.deque(maxlen=288)


def get_data():
    try:
        data = requests.get("http://127.0.0.1/data_seis.json", timeout=3).json()
        temperature = data["temperature"]
        humidity = data["humidity"]
        pressure = data["pressure"]
        create_at = data["create_at"][-8:]
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
    page.render(html_name)


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
