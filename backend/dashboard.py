from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from iot_pipeline.config import Settings
from iot_pipeline.influx_store import InfluxStore


st.set_page_config(
    page_title="TH02 IoT Data Monitoring",
    page_icon="📡",
    layout="wide",
)


@st.cache_resource
def load_runtime() -> tuple[Settings, InfluxStore]:
    settings = Settings.from_env()
    return settings, InfluxStore(settings)


def metric_value(frame: pd.DataFrame, column: str, suffix: str) -> str:
    if frame.empty or column not in frame.columns or frame[column].dropna().empty:
        return "--"
    return f"{frame[column].dropna().iloc[-1]:.2f}{suffix}"


def main() -> None:
    settings, store = load_runtime()
    st_autorefresh(
        interval=settings.dashboard_refresh_seconds * 1000,
        key="dashboard-refresh",
    )

    st.title("Bài thực hành số 2 - Giám sát dữ liệu IoT")
    st.caption(
        "ESP32 Wokwi → HiveMQ Cloud → Python → InfluxDB → Streamlit"
    )

    with st.sidebar:
        st.header("Bộ lọc")
        range_value = st.selectbox(
            "Khoảng thời gian", ("-15m", "-30m", "-1h", "-6h", "-1d"), index=2
        )
        st.write(f"Tự làm mới mỗi {settings.dashboard_refresh_seconds} giây")
        st.write(f"Topic: `{settings.mqtt_topic}`")

    try:
        raw = store.query_measurement(
            settings.influx_raw_bucket, "sensor_raw", start=range_value
        )
        processed = store.query_measurement(
            settings.influx_processed_bucket,
            "sensor_processed",
            start=range_value,
        )
    except Exception as exc:
        st.error(f"Không thể đọc InfluxDB: {exc}")
        st.stop()

    if raw.empty:
        st.info("Chưa có dữ liệu raw. Hãy chạy InfluxDB, collector và Wokwi.")
        st.stop()

    raw["_time"] = pd.to_datetime(raw["_time"], utc=True)
    raw = raw.sort_values("_time")
    if not processed.empty:
        processed["_time"] = pd.to_datetime(processed["_time"], utc=True)
        processed = processed.sort_values("_time")

    cards = st.columns(4)
    cards[0].metric("Nhiệt độ", metric_value(raw, "temperature", " °C"))
    cards[1].metric("Độ ẩm", metric_value(raw, "humidity", " %RH"))
    cards[2].metric("Khoảng cách", metric_value(raw, "distance_cm", " cm"))
    cards[3].metric("Độ trễ", metric_value(raw, "latency_ms", " ms"))

    st.subheader("Dữ liệu cảm biến thời gian thực")
    sensor_columns = [
        column
        for column in ("temperature", "humidity", "distance_cm")
        if column in raw.columns
    ]
    melted = raw.melt(
        id_vars="_time",
        value_vars=sensor_columns,
        var_name="Đại lượng",
        value_name="Giá trị",
    )
    st.plotly_chart(
        px.line(melted, x="_time", y="Giá trị", color="Đại lượng"),
        width="stretch",
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Dữ liệu raw và đã xử lý")
        if processed.empty:
            st.warning("Chưa có dữ liệu processed. Chạy `python preprocess.py`.")
        else:
            comparison_columns = [
                column
                for column in (
                    "temperature_raw",
                    "temperature_clean",
                    "temperature_rolling_mean",
                )
                if column in processed.columns
            ]
            comparison = processed.melt(
                id_vars="_time",
                value_vars=comparison_columns,
                var_name="Chuỗi",
                value_name="Nhiệt độ",
            )
            st.plotly_chart(
                px.line(comparison, x="_time", y="Nhiệt độ", color="Chuỗi"),
                width="stretch",
            )

    with right:
        st.subheader("Độ trễ end-to-end")
        if "latency_ms" in raw.columns:
            latency = raw["latency_ms"].dropna().astype(float)
            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=raw.loc[latency.index, "_time"],
                    y=latency,
                    mode="lines+markers",
                    name="latency_ms",
                )
            )
            st.plotly_chart(figure, width="stretch")
            stats = st.columns(3)
            stats[0].metric("Trung bình", f"{latency.mean():.1f} ms")
            stats[1].metric("P95", f"{latency.quantile(0.95):.1f} ms")
            stats[2].metric("Lớn nhất", f"{latency.max():.1f} ms")

    st.subheader("Chất lượng dữ liệu và sự kiện")
    quality = st.columns(4)
    quality[0].metric("Số bản ghi raw", len(raw))
    gap_total = int(raw.get("gap_count", pd.Series(dtype=float)).fillna(0).sum())
    quality[1].metric("Gói bị thiếu", gap_total)
    outlier_total = 0
    if not processed.empty and "is_outlier" in processed.columns:
        outlier_total = int(processed["is_outlier"].fillna(False).astype(bool).sum())
    quality[2].metric("Dòng outlier", outlier_total)
    latest_status = str(raw.get("sequence_status", pd.Series(["--"])).iloc[-1])
    quality[3].metric("Sequence gần nhất", latest_status)

    table_columns = [
        column
        for column in (
            "_time",
            "device_id",
            "sequence",
            "sequence_status",
            "gap_count",
            "latency_ms",
            "temperature",
            "humidity",
            "distance_cm",
        )
        if column in raw.columns
    ]
    st.dataframe(raw[table_columns].tail(20), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()

