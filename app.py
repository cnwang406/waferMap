from __future__ import annotations

version = "0.2.0"
appDescription = f"""Wafer Contour Viewer

by cnwang 2026/03.  v{version}

input : excel with siteX, siteY, thickness
parameters : stepX, stepY, offsetX, offsetY, frameOffsetX, frameOffsetY, diameter, flat
output : frame-only preview or contour plot, data table, JPG file

framework : streamlit, pandas, matplotlib, scipy.interpolate
"""


import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wafermap_core import (
    defaultDiameterMm,
    flatOptions,
    build_interpolated_grid,
    build_wafer_outline,
    calculate_positions,
    collapse_duplicate_points,
    count_points_outside_outline,
    figure_to_jpg_bytes,
    normalize_columns,
    render_figure,
    validate_parameters,
)


st.set_page_config(page_title=f"Wafer Contour Viewer, by cnwang {version}", layout="wide")
st.title("Wafer Thickness Contour")


st.caption(
    f"by cnwang 2026/03.  v{version}"
)

with st.sidebar:
    st.header("輸入參數")
    stepXUm = st.number_input("stepX (um)", min_value=0.0, value=10000.0, step=100.0)
    stepYUm = st.number_input("stepY (um)", min_value=0.0, value=10000.0, step=100.0)
    offsetXUm = st.number_input("offsetX (um)", min_value=0.0, value=0.0, step=10.0)
    offsetYUm = st.number_input("offsetY (um)", min_value=0.0, value=0.0, step=10.0)
    frameOffsetXUm = st.number_input("frame offset X (um)", value=0.0, step=10.0)
    frameOffsetYUm = st.number_input("frame offset Y (um)", value=0.0, step=10.0)
    diameterMm = st.number_input(
        "wafer diameter (mm)",
        min_value=1.0,
        value=defaultDiameterMm,
        step=1.0,
    )
    flatOption = st.selectbox("flat", list(flatOptions.keys()), index=0)
    showContour = st.checkbox("顯示 contour", value=True)
    showContourGrid = st.checkbox("顯示 contour grid", value=False)

uploadedFile = st.file_uploader("上傳 Excel 檔", type=["xlsx", "xls"])

try:
    validate_parameters(stepXUm, stepYUm, offsetXUm, offsetYUm, diameterMm)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

outline = build_wafer_outline(diameterMm=diameterMm, flatOption=flatOption)
plotDf = pd.DataFrame(columns=["posXMm", "posYMm", "thickness"])
calculatedDf = pd.DataFrame()
duplicateCount = 0
outsideCount = 0
contourGrid = None
hasExcelData = uploadedFile is not None
outputStem = "wafer_frame_preview"

if hasExcelData:
    fileBytes = uploadedFile.getvalue()
    fileName = Path(uploadedFile.name)
    outputStem = fileName.stem

    try:
        excelFile = pd.ExcelFile(io.BytesIO(fileBytes))
    except Exception as exc:  # pragma: no cover - streamlit runtime feedback
        st.error(f"無法讀取 Excel 檔案: {exc}")
        st.stop()

    sheetName = st.selectbox("選擇工作表", excelFile.sheet_names)

    try:
        rawDf = pd.read_excel(io.BytesIO(fileBytes), sheet_name=sheetName)
        sourceDf = normalize_columns(rawDf)
        sourceDf = sourceDf.apply(pd.to_numeric, errors="raise")
    except Exception as exc:  # pragma: no cover - streamlit runtime feedback
        st.error(f"資料格式錯誤: {exc}")
        st.stop()

    if sourceDf.empty:
        st.error("Excel 目前沒有可用資料列。")
        st.stop()

    calculatedDf = calculate_positions(
        sourceDf,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        offsetXUm=offsetXUm,
        offsetYUm=offsetYUm,
    )
    plotDf, duplicateCount = collapse_duplicate_points(calculatedDf)
    outsideCount = count_points_outside_outline(plotDf, outline)
    if showContour:
        contourGrid = build_interpolated_grid(plotDf, outline)
else:
    st.info("未上傳 Excel，僅使用 step/offset 參數顯示 wafer frames。")

title = outputStem
showContourEffective = showContour and hasExcelData

if showContour and not hasExcelData:
    st.caption("未提供 Excel，contour 已自動關閉。")

if duplicateCount:
    st.warning(
        f"偵測到 {duplicateCount} 筆重複座標，繪圖時已先對相同座標的 thickness 取平均。"
    )

if outsideCount:
    st.warning(f"有 {outsideCount} 個量測點落在 wafer 外框之外，請確認 step/offset 或來源資料。")

if showContourEffective and contourGrid is None:
    st.warning("可用點位不足以建立平滑 contour，將只顯示量測點與 thickness 標註。")

figure = render_figure(
    plotDf,
    outline,
    title,
    contourGrid,
    stepXUm=stepXUm,
    stepYUm=stepYUm,
    frameOffsetXUm=frameOffsetXUm,
    frameOffsetYUm=frameOffsetYUm,
    showContour=showContourEffective,
    showContourGrid=showContourGrid,
)
jpgBytes = figure_to_jpg_bytes(figure)
outputPath = Path.cwd() / f"{outputStem}.jpg"
outputPath.write_bytes(jpgBytes)

colChart, colData = st.columns([1.4, 1.0])

with colChart:
    st.pyplot(figure, use_container_width=True)
    st.download_button(
        label="下載 JPG",
        data=jpgBytes,
        file_name=f"{outputStem}.jpg",
        mime="image/jpeg",
    )
    st.success(f"JPG 已輸出為 {outputPath.name}")
    if flatOption == "notch":
        st.caption("notch 外框使用 6 mm 寬、2 mm 深的近似 V-notch。")

with colData:
    st.subheader("計算結果")
    if hasExcelData:
        st.dataframe(
            calculatedDf[["siteX", "siteY", "thickness", "posXUm", "posYUm", "posXMm", "posYMm"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("未提供 Excel，無量測資料表可顯示。")

plt.close(figure)
