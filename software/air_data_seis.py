# -*- coding: utf-8 -*-
import os
import json
import time
import struct
import serial
import datetime
import tempfile

SYNC_WORD = 0x8A
PACKET_SIZE = struct.calcsize("<fffB")

SERIAL_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
BAUDRATE = 19200

OUTPUT_FILE = "/var/www/html/data_seis.json"

# 超过多久没有成功拿到一帧有效数据，就认为“假死”并重连
STALE_SECONDS = 180  # 3分钟，你也可以改成 120/300
# 重连等待间隔
RECONNECT_SLEEP = 2


def now_str():
    return datetime.datetime.now().strftime("[%H:%M:%S]")


def calculate_checksum(data_bytes: bytes) -> int:
    cs = 0
    for b in data_bytes:
        cs ^= b
    return cs


def atomic_write_json(path: str, data: dict, mode: int = 0o644):
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # 关键：显式设定权限（不再受 umask 影响）
        os.chmod(tmp_path, mode)

        # 原子替换
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def open_serial(port_path: str, baudrate: int) -> serial.Serial:
    """
    打开串口（如果设备文件暂时不存在，就等待）
    """
    while True:
        try:
            if not os.path.exists(port_path):
                print(f"{now_str()} 串口路径不存在，等待设备出现喵… {port_path}")
                time.sleep(RECONNECT_SLEEP)
                continue

            ser = serial.Serial(
                port=port_path,
                baudrate=baudrate,
                timeout=1,  # 读超时短一点，便于快速检测异常/假死
                write_timeout=1,
                exclusive=True,  # 防止被其它进程抢占（Linux下有效）
            )

            # 清理缓冲区，避免重新插拔后残留脏数据
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            print(f"{now_str()} 已打开串口：{port_path} @ {baudrate}")
            time.sleep(0.5)
            return ser

        except (serial.SerialException, OSError) as e:
            print(f"{now_str()} 打开串口失败，稍后重试喵… 错误: {e}")
            time.sleep(RECONNECT_SLEEP)


def read_sensor_packet(ser: serial.Serial):
    """
    从串口读一帧。返回 dict 或 None。
    这里的关键是：不要无限等 SYNC；timeout=1 会让 read(1) 频繁返回空，从而上层可做“假死检测”。
    """
    # 找同步字节
    b = ser.read(1)
    if not b:
        return None

    if b[0] != SYNC_WORD:
        return None

    packet = ser.read(PACKET_SIZE)
    if len(packet) != PACKET_SIZE:
        return None

    float_bytes = packet[:12]
    recv_checksum = packet[12]

    if calculate_checksum(float_bytes) != recv_checksum:
        print(f"{now_str()} 校验失败，丢弃本次数据喵")
        return None

    temperature, humidity, pressure = struct.unpack("<fff", float_bytes)
    return {"temperature": temperature, "humidity": humidity, "pressure": pressure}


def main():
    ser = None
    last_good_time = 0.0
    last_write_time = 0.0

    print(f"启动喵～目标串口 {SERIAL_PORT}，波特率 {BAUDRATE}")

    while True:
        try:
            # 没有串口就打开
            if ser is None:
                ser = open_serial(SERIAL_PORT, BAUDRATE)
                last_good_time = time.time()

            sensor = read_sensor_packet(ser)

            # 成功读到一帧
            if sensor:
                last_good_time = time.time()

                data = {
                    "temperature": sensor["temperature"],
                    "humidity": sensor["humidity"],
                    "pressure": sensor["pressure"],
                    "create_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                # 按你的逻辑：每次成功后写入，然后 sleep 60s
                atomic_write_json(OUTPUT_FILE, data)
                last_write_time = time.time()
                print(f"{now_str()} 写入数据: {data}")

                time.sleep(60)
                continue

            # 没读到：做“假死检测”
            if time.time() - last_good_time > STALE_SECONDS:
                raise RuntimeError(
                    f"超过 {STALE_SECONDS}s 未收到有效数据，判定串口假死，重连喵"
                )

            time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n退出程序喵～")
            break

        except (serial.SerialException, OSError) as e:
            # 典型掉线异常
            print(f"{now_str()} 串口异常/掉线，准备重连喵… 错误: {e}")

            try:
                if ser is not None:
                    ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(RECONNECT_SLEEP)

        except Exception as e:
            # 其它异常（含假死触发）
            print(f"{now_str()} 异常，准备重连喵… 错误: {e}")

            try:
                if ser is not None:
                    ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(RECONNECT_SLEEP)

    # 收尾
    try:
        if ser is not None:
            ser.close()
            print("串口已关闭喵～")
    except Exception:
        pass


if __name__ == "__main__":
    main()
