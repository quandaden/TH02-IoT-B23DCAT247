# Danh sách ảnh minh chứng Bài thực hành số 2

Chỉ chụp sau khi cửa sổ đã được thu gọn hợp lý. Không để lộ MQTT password, InfluxDB token, file `.env` hoặc `include/secrets.h`.

## 01 Wokwi publish

Tên file: `01_wokwi_publish.png`

Chụp cửa sổ VS Code Wokwi gồm mạch và Serial Monitor. Ảnh phải thấy:

- ESP32, DHT22, HC-SR04 và LED.
- `MQTT: connected`.
- Một dòng `PUBLISH ... status=OK`.
- Payload có `device_id`, `sent_at_ms`, `temperature`, `humidity`, `distance_cm` và `sequence`.

Đây là ảnh người dùng cần chụp đầu tiên sau khi điền HiveMQ credentials và chạy mô phỏng.

## 02 Collector ingest

Tên file: `02_collector_ingest.png`

Chụp terminal collector có các dòng:

- `MQTT connected` và `MQTT subscribed`.
- Ít nhất ba dòng `INGEST OK`.
- Nhìn thấy `sequence`, `latency_ms` và ba giá trị cảm biến.

## 03 InfluxDB raw

Tên file: `03_influxdb_raw.png`

Chụp Data Explorer của InfluxDB với measurement `sensor_raw`, khoảng 10-20 bản ghi và các cột `_time`, `device_id`, `temperature`, `humidity`, `distance_cm`, `sequence`, `latency_ms`.

## 04 Dữ liệu đã xử lý

Tên file: `04_processed_data.png`

Chụp kết quả lệnh `python backend/preprocess.py` hoặc Data Explorer của measurement `sensor_processed`. Cần thấy `temperature_raw`, `temperature_clean`, `temperature_rolling_mean`, `temperature_normalized` và `is_outlier`.

## 05 Dashboard

Tên file: `05_dashboard.png`

Chụp toàn màn hình Streamlit gồm bốn card hiện tại, biểu đồ raw, biểu đồ raw/clean/rolling mean, biểu đồ latency và thống kê chất lượng dữ liệu.

## 06 Lỗi và khôi phục

Tên file: `06_error_recovery.png`

Chụp terminal collector sau khi chạy công cụ test với `--include-errors`. Ảnh cần có một dòng `VALIDATION REJECTED`, một dòng `SEQUENCE SKIPPED` hoặc `status=gap`, và một dòng `INGEST OK` sau đó.

