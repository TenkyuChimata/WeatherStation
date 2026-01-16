# -*- coding: utf-8 -*-
import os
import json
import time
import struct
import serial
import datetime
import collections

# 同步字节
SYNC_WORD = 0x8A
# 8 个 float（4 字节 * 8） + 1 字节校验
PACKET_SIZE = struct.calcsize("<8fB")

usv_list = collections.deque(maxlen=60)


def avg(arr):
    if not arr:
        return 0.0
    return sum(arr) / len(arr)


def calculate_checksum(data_bytes: bytes) -> int:
    """对一段 bytes 做异或校验"""
    cs = 0
    for b in data_bytes:
        cs ^= b
    return cs


def read_exact(ser: serial.Serial, n: int) -> bytes:
    """
    尽量读满 n 字节。
    - 超时可能读不到那么多：返回实际读取到的 bytes（可能为空）
    - 断线时可能抛 SerialException / OSError
    """
    buf = bytearray()
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return bytes(buf)


def read_sensor_packet(ser: serial.Serial):
    """从串口不断读，找到 SYNC_WORD 后读取一个完整数据包并解析"""
    # 等待同步字节（一直扫，直到读到 0x8A）
    while True:
        b = ser.read(1)
        if not b:
            return None  # 超时
        if b[0] == SYNC_WORD:
            break

    # 读出后面的数据包（尽量读满）
    packet = read_exact(ser, PACKET_SIZE)
    if len(packet) != PACKET_SIZE:
        return None

    float_bytes = packet[:32]  # 前 32 字节是 8 个 float
    recv_checksum = packet[32]  # 最后一字节是校验（int）

    if calculate_checksum(float_bytes) != recv_checksum:
        print(
            f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 校验失败，丢弃本次数据"
        )
        return None

    (
        temperature,
        humidity,
        pressure_hpa,
        usv,
        pm1p0,
        pm2p5,
        pm4p0,
        pm10,
    ) = struct.unpack("<8f", float_bytes)

    return {
        "temperature": float(temperature),
        "humidity": float(humidity),
        "pressure": float(pressure_hpa),
        "pm1.0": float(pm1p0),
        "pm2.5": float(pm2p5),
        "pm4.0": float(pm4p0),
        "pm10": float(pm10),
        "usv": float(usv),
    }


def atomic_write_json(path: str, data: dict):
    """
    原子写入 JSON：先写临时文件，再 os.replace 覆盖，避免读到半截文件。
    """
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def open_serial_forever(
    port: str, baudrate: int, timeout: float = 5.0
) -> serial.Serial:
    """
    永远尝试打开串口，直到成功。
    """
    while True:
        try:
            ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
            # 给设备一点缓冲时间（尤其是 USB-Serial 刚连上）
            time.sleep(2)
            # 清一下可能残留的缓冲区，减少“半包”概率
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            print(
                f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 已连接串口: {port}"
            )
            return ser
        except Exception as e:
            print(
                f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 打开串口失败，2 秒后重试喵～ {e}"
            )
            time.sleep(2)


def main():
    serial_port = "/dev/station"
    baudrate = 115200

    output_json = "/var/www/html/data.json"

    print(f"使用稳定串口路径: {serial_port}，波特率 {baudrate}")
    ser = open_serial_forever(serial_port, baudrate, timeout=5)

    try:
        while True:
            try:
                sensor = read_sensor_packet(ser)

                if sensor:
                    usv_list.append(sensor["usv"])

                    data = {
                        "temperature": sensor["temperature"],
                        "humidity": sensor["humidity"],
                        "pressure": sensor["pressure"],
                        "pm1.0": sensor["pm1.0"],
                        "pm2.5": sensor["pm2.5"],
                        "pm4.0": sensor["pm4.0"],
                        "pm10": sensor["pm10"],
                        "usv": sensor["usv"],
                        "usv_avg": avg(usv_list),
                        "create_at": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }

                    atomic_write_json(output_json, data)

                    print(
                        f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 写入数据: {data}"
                    )
                    time.sleep(0.1)
                else:
                    # 没读到有效包就稍微歇一下，避免空转占 CPU
                    time.sleep(0.1)

            except (serial.SerialException, OSError) as e:
                # 断线/多进程抢占/设备异常：关闭并重连
                print(
                    f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 串口断开/异常，准备重连喵～ {e}"
                )
                try:
                    ser.close()
                except Exception:
                    pass
                time.sleep(1)
                ser = open_serial_forever(serial_port, baudrate, timeout=5)

            except Exception as e:
                # 其它异常：不中断主循环
                print(
                    f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 本轮异常，继续运行喵～ 错误: {e}"
                )
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n退出程序喵～")

    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
