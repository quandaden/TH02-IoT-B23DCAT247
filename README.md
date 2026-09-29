# Bài thực hành số 2 IoT

Project kế thừa nút cảm biến ESP32 của Bài thực hành số 1 và bổ sung pipeline HiveMQ chạy bằng Docker, Python, InfluxDB, tiền xử lý dữ liệu và dashboard Streamlit.

## Kiến trúc

```text
ESP32 trên Wokwi
  -> host.wokwi.internal:1883
HiveMQ Docker trên máy host
  -> Python collector
  -> InfluxDB iot_raw
  -> Python preprocessor
  -> InfluxDB iot_processed
  -> Streamlit dashboard
```

## 1. Kiểm tra HiveMQ Docker

Broker được chạy bằng container `hivemq/hivemq4:latest` và publish cổng MQTT `1883` ra Windows. Kiểm tra bằng:

```powershell
docker ps --filter name=hivemq
Test-NetConnection 127.0.0.1 -Port 1883
```

Firmware Wokwi truy cập máy Windows bằng `host.wokwi.internal:1883`. Python collector chạy trên Windows nên dùng `127.0.0.1:1883`.

## 2. Cấu hình firmware Wokwi

Project đã có file cấu hình cục bộ. Nếu cần tạo lại, sao chép file mẫu:

```powershell
Copy-Item include\secrets.example.h include\secrets.h
```

Các giá trị mặc định trong `include/secrets.h`:

- `MQTT_HOST`: `host.wokwi.internal`.
- `MQTT_PORT`: `1883`.
- `MQTT_USERNAME` và `MQTT_PASSWORD`: để trống khi HiveMQ cho phép anonymous.
- `MQTT_TLS_ENABLED`: `false`.
- Topic: `ptit/b23dcat247/sensors`.

Build và chạy bằng PlatformIO/Wokwi:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run
```

Sau khi Serial Monitor xuất hiện `MQTT: connected` và `PUBLISH ... status=OK`, chụp ảnh `01_wokwi_publish.png` theo `docs/screenshot-checklist.md`.

## 3. Cấu hình Python và InfluxDB

Tại thư mục project:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Trong `.env`, giữ `MQTT_HOST=127.0.0.1`, `MQTT_PORT=1883` và để username/password trống. Thay hai giá trị InfluxDB password/token bằng chuỗi mạnh. Giữ `.env` ngoài Git.

Khởi động InfluxDB:

```powershell
docker compose --env-file .env up -d
python backend\bootstrap_influx.py
```

Giao diện InfluxDB: `http://localhost:8086`.

## 4. Chạy collector

```powershell
python backend\collector.py
```

Chạy Wokwi ở terminal khác. Collector phải xuất hiện `INGEST OK`. Chụp `02_collector_ingest.png`, sau đó mở InfluxDB Data Explorer để chụp `03_influxdb_raw.png`.

Có thể kiểm tra một payload mà không cần broker hoặc database:

```powershell
python backend\collector.py --check-payload '{"device_id":"esp32-test","sent_at_ms":1790672400000,"temperature":25,"humidity":50,"distance_cm":100,"rssi":-70,"sequence":1,"uptime_s":5}'
```

## 5. Tiền xử lý

Sau khi đã thu thập ít nhất 5-10 phút dữ liệu:

```powershell
python backend\preprocess.py --start=-1h
```

Script thực hiện resampling 10 giây, nội suy missing values, phát hiện outlier IQR, tạo clean value, rolling mean, delta và z-score. Chụp `04_processed_data.png`.

## 6. Dashboard

```powershell
streamlit run backend\dashboard.py
```

Mở địa chỉ Streamlit được in trong terminal, thường là `http://localhost:8501`, rồi chụp `05_dashboard.png`.

## 7. Minh chứng xử lý lỗi

Trong terminal mới:

```powershell
Set-Location backend
python -m tools.publish_test_data --include-errors
```

Quan sát terminal collector và chụp `06_error_recovery.png`.

## 8. Chạy kiểm thử

```powershell
Set-Location backend
python -m unittest discover -s tests -v
```

## Dữ liệu thử nghiệm đề xuất

Giữ mỗi trạng thái Wokwi từ 30 đến 60 giây:

| Lần | Nhiệt độ | Độ ẩm | Khoảng cách |
|---:|---:|---:|---:|
| 1 | 20 °C | 35% | 20 cm |
| 2 | 25 °C | 50% | 50 cm |
| 3 | 30 °C | 65% | 100 cm |
| 4 | 35 °C | 80% | 200 cm |
| 5 | 70 °C | 55% | 400 cm |

## An toàn thông tin

- `include/secrets.h` và `.env` đã được `.gitignore` loại khỏi repository.
- Broker hiện dùng MQTT không mã hóa trên cổng `1883` và chỉ phù hợp với môi trường lab cục bộ. Triển khai thật phải mở `8883`, cấu hình chứng thư máy chủ, bật `MQTT_TLS_ENABLED` và xác minh CA.
- Nếu token ThingsBoard của bài 1 từng xuất hiện trong mã nguồn hoặc báo cáo, cần thu hồi và tạo token mới.

