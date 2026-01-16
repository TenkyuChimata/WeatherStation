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
radiation_list = collections.deque(maxlen=288)
radiation_avg_list = collections.deque(maxlen=288)
pm25_list = collections.deque(maxlen=288)
pm10_list = collections.deque(maxlen=288)
createat_list = collections.deque(maxlen=288)


def get_data():
    try:
        data = requests.get("http://127.0.0.1/data.json", timeout=3).json()
        radiation = data["usv"]
        radiation_avg = data["usv_avg"]
        temperature = data["temperature"]
        humidity = data["humidity"]
        pressure = data["pressure"]
        pm25 = data["pm2.5"]
        pm10 = data["pm10"]
        create_at = data["create_at"][-8:]
    except Exception as e:
        print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
        return None
    return (
        temperature,
        humidity,
        pressure,
        radiation,
        radiation_avg,
        pm25,
        pm10,
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
            radiation_list.append(weather_data[3])
            radiation_avg_list.append(weather_data[4])
            pm25_list.append(weather_data[5])
            pm10_list.append(weather_data[6])
            createat_list.append(weather_data[7])
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
                list(pm25_list),
                "PM2.5 (μg/m³)",
                "PM2.5",
                "/var/www/html/pm2.5.html",
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
