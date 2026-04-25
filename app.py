from __future__ import annotations

version = "1.3"
appDescription = f"""Wafer Contour Viewer

by cnwang 2026/03.  v{version}

input : excel with siteX, siteY, thickness
parameters : stepX, stepY, offsetX, offsetY, frameOffsetX, frameOffsetY, diameter, flat
output : frame-only preview or contour plot, data table, JPG file

framework : streamlit, pandas, matplotlib, numpy
"""


import re
import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import json
from wafermap_core import (
    build_complete_frame_rectangles,
    build_complete_die_rectangles,
    build_effective_outline,
    defaultDiameterMm,
    flatOptions,
    build_interpolated_grid,
    build_wafer_outline,
    calculate_positions,
    collapse_duplicate_points,
    count_points_outside_outline,
    figure_to_jpg_bytes,
    render_figure,
    top_y_at_x,
    validate_parameters,
)
from kgdmapviewer import render_kgdmap_viewer


def sanitize_file_stem(rawText: str) -> str:
    cleanedText = re.sub(r'[\\/:*?"<>|]+', "_", rawText.strip())
    cleanedText = re.sub(r"\s+", "_", cleanedText)
    cleanedText = cleanedText.strip("._")
    return cleanedText or "wafer_frame_preview"


def normalize_parameter_name(rawText: object) -> str:
    if pd.isna(rawText):
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(rawText).strip().lower())


def detect_csv_format(fileBytes: bytes, fileName: str) -> tuple[str, pd.DataFrame | None]:
    """
    Detect CSV format type:
    - 'kgdmap': KGDmap format with header (rows 1-10) and data (rows 12+)
    - 'normal': Standard x,y,value format
    - 'unknown': Cannot determine format
    
    Returns: (format_type, dataframe_or_none)
    """
    try:
        # First, try to detect KGDmap by reading just the first 10 lines
        lines = fileBytes.decode('utf-8').split('\n')[:12]
        
        # Check if first column values match KGDmap pattern
        kgdmap_keywords = {'lot', 'wafer', 'date', 'time', 'programname', 'testername'}
        first_col_keywords = []
        
        for i in range(min(10, len(lines))):
            parts = lines[i].split(',')
            if parts:
                first_col_keywords.append(parts[0].lower().strip())
        
        # If first 10 rows start with KGDmap keywords, treat as KGDmap
        if any(kw in kgdmap_keywords for kw in first_col_keywords[:5]):
            # Read as KGDmap format
            # Skip first 10 rows (0-9), use row 11 (index 10) as header, read from row 12 (index 11)
            df = pd.read_csv(io.BytesIO(fileBytes), skiprows=10, header=0)
            return "kgdmap", df
        
        # Otherwise try normal CSV format
        df = pd.read_csv(io.BytesIO(fileBytes))
        if len(df.columns) >= 3:
            return "normal", df
        
        return "unknown", None
    except Exception as e:
        return "unknown", None


def extract_kgdmap_header(fileBytes: bytes) -> dict:
    """
    Extract KGDmap header information from first 10 rows.
    """
    header_info = {}
    try:
        lines = fileBytes.decode('utf-8').split('\n')[:10]
        for line in lines:
            parts = line.split(',', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key:
                    header_info[key] = value
    except Exception:
        pass
    return header_info


def parse_flat_value(rawValue: object) -> str | None:
    text = str(rawValue).strip().lower()
    if text in {"47.5", "47.5mm", "47.5 mm"}:
        return "47.5 mm"
    if text in {"57.5", "57.5mm", "57.5 mm"}:
        return "57.5 mm"
    if text in {"notch", "notch180", "notch-180", "notch 180"}:
        return "notch-180"
    if text in {"notch135", "notch-135", "notch 135"}:
        return "notch-135"
    valueNumber = pd.to_numeric(pd.Series([rawValue]), errors="coerce").iloc[0]
    if pd.notna(valueNumber):
        if abs(float(valueNumber) - 47.5) < 0.5:
            return "47.5 mm"
        if abs(float(valueNumber) - 57.5) < 0.5:
            return "57.5 mm"
    return None


def parse_measurement_table(rawSheetDf: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    if rawSheetDf.shape[1] < 3:
        raise ValueError("Excel 至少需要 3 欄資料（X, Y, value）。")
    if rawSheetDf.empty:
        raise ValueError("Excel 目前沒有可用資料列。")

    firstRow = rawSheetDf.iloc[0, :3]
    firstTwoNumeric = pd.to_numeric(firstRow.iloc[:2], errors="coerce")
    thirdNumeric = pd.to_numeric(pd.Series([firstRow.iloc[2]]), errors="coerce").iloc[0]

    dataStartRow = 0
    valueLabel = "thickness"
    if firstTwoNumeric.isna().all():
        dataStartRow = 1
        valueHeader = str(firstRow.iloc[2]).strip()
        if valueHeader:
            valueLabel = valueHeader
    elif pd.notna(firstTwoNumeric.iloc[0]) and pd.notna(firstTwoNumeric.iloc[1]) and pd.isna(thirdNumeric):
        dataStartRow = 1
        valueHeader = str(firstRow.iloc[2]).strip()
        if valueHeader:
            valueLabel = valueHeader

    dataBlock = rawSheetDf.iloc[dataStartRow:, :3].copy()
    dataBlock.columns = ["siteX", "siteY", "thickness"]
    dataBlock = dataBlock.apply(pd.to_numeric, errors="coerce")
    dataBlock = dataBlock.dropna(subset=["siteX", "siteY", "thickness"]).reset_index(drop=True)
    if dataBlock.empty:
        raise ValueError("找不到可用的數值資料列。請確認前三欄內容。")

    hasFloatingCoord = (
        ((dataBlock["siteX"] - dataBlock["siteX"].round()).abs() > 1e-9).any()
        or ((dataBlock["siteY"] - dataBlock["siteY"].round()).abs() > 1e-9).any()
    )
    coordinateMode = "mm" if hasFloatingCoord else "index"
    return dataBlock, valueLabel, coordinateMode


def parse_parameter_overrides(rawSheetDf: pd.DataFrame) -> tuple[dict[str, object], bool]:
    if rawSheetDf.shape[1] < 5:
        return {}, False

    parameterNameMap = {
        "stepx": "stepXUm",
        "stepy": "stepYUm",
        "frameoffsetx": "frameOffsetXUm",
        "frameoffsety": "frameOffsetYUm",
        "arrayx": "arrayX",
        "arrayy": "arrayY",
        "top": "topMm",
        "offsetx": "offsetXUm",
        "offsety": "offsetYUm",
        "diameter": "diameterMm",
        "waferdiameter": "diameterMm",
        "flat": "flatOption",
        "edgeexclude": "edgeExcludeMm",
        "bottom": "bottomMm",
    }

    overrides: dict[str, object] = {}
    hasParameterData = False
    for row in rawSheetDf.itertuples(index=False):
        if len(row) < 5:
            continue
        rawName = row[3]
        rawValue = row[4]
        normalizedName = normalize_parameter_name(rawName)
        targetKey = parameterNameMap.get(normalizedName)
        if not targetKey or pd.isna(rawValue):
            continue

        hasParameterData = True
        if targetKey == "flatOption":
            flatValue = parse_flat_value(rawValue)
            if flatValue is not None:
                overrides[targetKey] = flatValue
            continue

        parsedValue = pd.to_numeric(pd.Series([rawValue]), errors="coerce").iloc[0]
        if pd.isna(parsedValue):
            continue
        if targetKey in {"arrayX", "arrayY"}:
            overrides[targetKey] = max(1, int(round(float(parsedValue))))
        else:
            overrides[targetKey] = float(parsedValue)

    return overrides, hasParameterData


def apply_parameter_overrides(overrides: dict[str, object]) -> bool:
    changed = False
    for key, value in overrides.items():
        currentValue = st.session_state.get(key)
        if isinstance(value, float) and isinstance(currentValue, (int, float)):
            if abs(float(currentValue) - value) <= 1e-9:
                continue
        elif currentValue == value:
            continue
        st.session_state[key] = value
        changed = True
    return changed


def build_parameter_rows(
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    arrayX: int,
    arrayY: int,
    topMm: float,
    offsetXUm: float,
    offsetYUm: float,
    diameterMm: float,
    flatOption: str,
    edgeExcludeMm: float,
    bottomMm: float,
) -> list[tuple[str, object]]:
    return [
        ("stepX", float(stepXUm)),
        ("stepY", float(stepYUm)),
        ("frameOffsetX", float(frameOffsetXUm)),
        ("frameOffsetY", float(frameOffsetYUm)),
        ("arrayX", int(arrayX)),
        ("arrayY", int(arrayY)),
        ("top", float(topMm)),
        ("offsetX", float(offsetXUm)),
        ("offsetY", float(offsetYUm)),
        ("diameter", float(diameterMm)),
        ("flat", flatOption),
        ("edge exclude", float(edgeExcludeMm)),
        ("bottom", float(bottomMm)),
    ]


def build_sheet_with_parameter_columns(
    rawSheetDf: pd.DataFrame, parameterRows: list[tuple[str, object]]
) -> pd.DataFrame:
    outputDf = rawSheetDf.copy()
    outputRows = max(len(outputDf), len(parameterRows) + 1)
    outputDf = outputDf.reindex(range(outputRows))
    while outputDf.shape[1] < 5:
        outputDf[outputDf.shape[1]] = pd.NA
    outputDf.iat[0, 3] = "parameter"
    outputDf.iat[0, 4] = "value"
    for rowIndex, (parameterName, parameterValue) in enumerate(parameterRows, start=1):
        outputDf.iat[rowIndex, 3] = parameterName
        outputDf.iat[rowIndex, 4] = parameterValue
    return outputDf


def build_excel_bytes(sheetTables: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheetName, sheetDf in sheetTables.items():
            sheetDf.to_excel(writer, sheet_name=sheetName, index=False, header=False)
    buffer.seek(0)
    return buffer.getvalue()


def build_info_panel_text(
    stepXUm: float,
    stepYUm: float,
    arrayX: int,
    arrayY: int,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    bottomMm: float,
    totalFrames: int,
    totalDies: int,
    frameBottomGapMm: float,
    offsetXUm: float,
    offsetYUm: float,
    diameterMm: float,
    flatOption: str,
    edgeExcludeMm: float,
    showContour: bool,
    contourStyle: str,
    showContourGrid: bool,
    coordinateMode: str,
    valueLabel: str,
    title: str,
    excelName: str,
) -> str:
    contourText = "ON" if showContour else "OFF"
    gridText = "ON" if showContourGrid else "OFF"
    bottomGapText = f"{frameBottomGapMm:.2f} mm" if frameBottomGapMm >= 0 else "N/A"
    lines = [
        f"title: {title}",
        f"contour data: {excelName}",
        f"value: {valueLabel}",
        f"coord mode: {coordinateMode}",
        "",
        f"frame W: {stepXUm:.1f} um",
        f"frame H: {stepYUm:.1f} um",
        f"arrayX: {arrayX}",
        f"arrayY: {arrayY}",
        f"frameOffsetX: {frameOffsetXUm:.1f} um",
        f"frameOffsetY: {frameOffsetYUm:.1f} um",
        f"top: {topMm:.2f} mm",
        f"bottom: {bottomMm:.2f} mm",
        f"total frames: {totalFrames}",
        f"total dies: {totalDies}",
        f"frame bottom gap: {bottomGapText}",
        "",
        f"site offset X (left-bottom): {offsetXUm:.1f} um",
        f"site offset Y (left-bottom): {offsetYUm:.1f} um",
        "",
        f"diameter: {diameterMm:.1f} mm",
        f"flat: {flatOption}",
        f"edge exclude: {edgeExcludeMm:.2f} mm",
        "",
        f"contour map: {contourText}",
        f"contour style: {contourStyle}",
        f"contour grid: {gridText}",
    ]
    return "\n".join(lines)


st.set_page_config(page_title=f"Wafer Contour Viewer, by cnwang {version}", layout="wide")
st.title("Wafer Thickness Contour")


st.caption(
    f"by cnwang 2026/03.  v{version}"
)

defaultStateValues = {
    "stepXUm": 10000.0,
    "stepYUm": 10000.0,
    "frameOffsetXUm": 0.0,
    "frameOffsetYUm": 0.0,
    "arrayX": 1,
    "arrayY": 1,
    "topMm": 10.0,
    "offsetXUm": 0.0,
    "offsetYUm": 0.0,
    "diameterMm": defaultDiameterMm,
    "flatOption": "57.5 mm",
    "edgeExcludeMm": 2.5,
    "bottomMm": 3.0,
    "showLaserMark": False,
    "laserMarkEdgeToTopMm": 3.0,
    "laserMarkCharHeightMm": 1.3,
    "laserMarkLengthMm": 11.0,
    "laserMarkPositionDeg": 0.0,
}
for stateKey, defaultValue in defaultStateValues.items():
    if stateKey not in st.session_state:
        st.session_state[stateKey] = defaultValue

uploadedFile = None
hasExcelData = False
fileBytes = b""
fileName = Path("wafer_frame_preview.xlsx")
excelFile: pd.ExcelFile | None = None
sheetName = ""
rawSheetDf = pd.DataFrame()
hasParameterColumns = False
kgdmapData: pd.DataFrame | None = None
isKGDmapFormat = False

with st.sidebar:
    st.header("輸入參數")
    uploadedFile = st.file_uploader("上傳 Excel/CSV 檔", type=["xlsx", "xls", "csv"])
    hasExcelData = uploadedFile is not None
    
    if hasExcelData:
        fileBytes = uploadedFile.getvalue()
        fileName = Path(uploadedFile.name)
        file_extension = fileName.suffix.lower()
        
        if file_extension == ".csv":
            # Handle CSV file
            try:
                csv_format, csv_df = detect_csv_format(fileBytes, fileName.name)
                
                if csv_format == "kgdmap":
                    # KGDmap format detected
                    isKGDmapFormat = True
                    kgdmapData = csv_df
                    # Extract header information
                    header_info = extract_kgdmap_header(fileBytes)
                    st.session_state["kgdmapData"] = csv_df
                    st.session_state["kgdmapHeader"] = header_info
                    st.session_state["kgdmapFileName"] = fileName.name
                    st.success(f"KGDmap 格式偵測成功: {fileName.name}")
                    st.info("KGDmap 數據已準備就緒，將在 Special View tab 中顯示")
                    
                elif csv_format == "normal":
                    # Normal CSV with x,y,value format
                    rawSheetDf = csv_df
                    sheetName = "CSV Data"
                    parameterOverrides, hasParameterColumns = parse_parameter_overrides(rawSheetDf)
                    parameterSourceToken = f"{fileName.name}:{len(fileBytes)}:csv"
                    if st.session_state.get("parameterSourceToken") != parameterSourceToken:
                        st.session_state["parameterSourceToken"] = parameterSourceToken
                        if parameterOverrides and apply_parameter_overrides(parameterOverrides):
                            st.rerun()
                else:
                    st.error(f"無法識別 CSV 格式: {fileName.name}")
                    st.stop()
                    
            except Exception as exc:
                st.error(f"無法讀取 CSV 檔案: {exc}")
                st.stop()
        else:
            # Handle Excel file
            try:
                excelFile = pd.ExcelFile(io.BytesIO(fileBytes))
            except Exception as exc:
                st.error(f"無法讀取 Excel 檔案: {exc}")
                st.stop()
            sheetName = st.selectbox("選擇工作表", excelFile.sheet_names, key="sheetName")
            try:
                rawSheetDf = pd.read_excel(io.BytesIO(fileBytes), sheet_name=sheetName, header=None)
            except Exception as exc:
                st.error(f"資料格式錯誤: {exc}")
                st.stop()
            parameterOverrides, hasParameterColumns = parse_parameter_overrides(rawSheetDf)
            parameterSourceToken = f"{fileName.name}:{len(fileBytes)}:{sheetName}"
            if st.session_state.get("parameterSourceToken") != parameterSourceToken:
                st.session_state["parameterSourceToken"] = parameterSourceToken
                if parameterOverrides and apply_parameter_overrides(parameterOverrides):
                    st.rerun()

    with st.container(border=True):
        st.caption("Frame Step / Frame Offset")
        columnA, columnB = st.columns(2)
        with columnA:
            stepXUm = st.number_input("stepX (um)", min_value=0.0, step=100.0, key="stepXUm")
            frameOffsetXUm = st.number_input("frame offset X (um)", step=10.0, key="frameOffsetXUm")
        with columnB:
            stepYUm = st.number_input("stepY (um)", min_value=0.0, step=100.0, key="stepYUm")
            frameOffsetYUm = st.number_input("frame offset Y (um)", step=10.0, key="frameOffsetYUm")
        arrayColA, arrayColB = st.columns(2)
        with arrayColA:
            arrayX = st.number_input("arrayX", min_value=1, step=1, format="%d", key="arrayX")
        with arrayColB:
            arrayY = st.number_input("arrayY", min_value=1, step=1, format="%d", key="arrayY")
        topMm = st.number_input("top (mm)", min_value=0.0, step=0.1, key="topMm")

    with st.container(border=True):
        st.caption("Site Offset")
        offsetXUm = st.number_input(
            "offsetX from frame left-bottom (um)", step=10.0, key="offsetXUm"
        )
        offsetYUm = st.number_input(
            "offsetY from frame left-bottom (um)", step=10.0, key="offsetYUm"
        )

    with st.container(border=True):
        st.caption("Wafer")
        diameterMm = st.number_input(
            "wafer diameter (mm)",
            min_value=1.0,
            step=1.0,
            key="diameterMm",
        )
        flatOption = st.selectbox(
            "flat", list(flatOptions.keys()), key="flatOption"
        )
        edgeExcludeMm = st.number_input("edge exclude (mm)", min_value=0.0, step=0.1, key="edgeExcludeMm")
        bottomMm = st.number_input("bottom (mm)", min_value=0.0, step=0.1, key="bottomMm")

    with st.container(border=True):
        st.caption("Laser Mark")
        showLaserMark = st.checkbox("enable lasermark frame", key="showLaserMark")
        laserMarkEdgeToTopMm = st.number_input(
            "edge-to-mark_top (mm)", min_value=0.0, step=0.1, key="laserMarkEdgeToTopMm"
        )
        laserMarkCharHeightMm = st.number_input(
            "char-height (mm)", min_value=0.1, step=0.1, key="laserMarkCharHeightMm"
        )
        laserMarkLengthMm = st.number_input(
            "marker length (mm)", min_value=0.1, step=0.1, key="laserMarkLengthMm"
        )
        laserMarkPositionDeg = st.number_input(
            "position (deg)", step=1.0, key="laserMarkPositionDeg"
        )

    with st.container(border=True):
        st.caption("Save / Load Configuration")
        if st.button("Save Config"):
            config_data = {
                "stepXUm": st.session_state.get("stepXUm", 10000.0),
                "stepYUm": st.session_state.get("stepYUm", 10000.0),
                "frameOffsetXUm": st.session_state.get("frameOffsetXUm", 0.0),
                "frameOffsetYUm": st.session_state.get("frameOffsetYUm", 0.0),
                "arrayX": st.session_state.get("arrayX", 1),
                "arrayY": st.session_state.get("arrayY", 1),
                "topMm": st.session_state.get("topMm", 10.0),
                "offsetXUm": st.session_state.get("offsetXUm", 0.0),
                "offsetYUm": st.session_state.get("offsetYUm", 0.0),
                "diameterMm": st.session_state.get("diameterMm", defaultDiameterMm),
                "flatOption": st.session_state.get("flatOption", "57.5 mm"),
                "edgeExcludeMm": st.session_state.get("edgeExcludeMm", 2.5),
                "bottomMm": st.session_state.get("bottomMm", 3.0),
                "showLaserMark": st.session_state.get("showLaserMark", False),
                "laserMarkEdgeToTopMm": st.session_state.get("laserMarkEdgeToTopMm", 3.0),
                "laserMarkCharHeightMm": st.session_state.get("laserMarkCharHeightMm", 1.3),
                "laserMarkLengthMm": st.session_state.get("laserMarkLengthMm", 11.0),
                "laserMarkPositionDeg": st.session_state.get("laserMarkPositionDeg", 0.0),
                "showContour": st.session_state.get("showContour", True),
                "contourStyle": st.session_state.get("contourStyle", "filled"),
                "showContourGrid": st.session_state.get("showContourGrid", False),
                "showInfoPanel": st.session_state.get("showInfoPanel", False),
                "frameLineColor": st.session_state.get("frameLineColor", "#f4a3a3"),
                "dieLineColor": st.session_state.get("dieLineColor", "#ececec"),
                "effectiveEdgeColor": st.session_state.get("effectiveEdgeColor", "#f4a3a3"),
                "waferEdgeColor": st.session_state.get("waferEdgeColor", "#000000"),
                "contourGridColor": st.session_state.get("contourGridColor", "#d9d9d9"),
                "inputTitle": st.session_state.get("inputTitle", "wafer_frame_preview"),
            }
            st.session_state["config_json"] = json.dumps(config_data, indent=2)
            st.success("Configuration prepared for download!")
        
        if "config_json" in st.session_state:
            st.download_button(
                label="Download Config JSON",
                data=st.session_state["config_json"],
                file_name="wafer_config.json",
                mime="application/json",
            )
        
        uploaded_config = st.file_uploader("Load Config JSON", type=["json"], key="config_uploader")
        if uploaded_config is not None:
            if st.button("Apply Config"):
                try:
                    config_data = json.loads(uploaded_config.getvalue().decode("utf-8"))
                    for key, value in config_data.items():
                        st.session_state[key] = value
                    if "config_json" in st.session_state:
                        del st.session_state["config_json"]
                    st.success("Configuration loaded successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load config: {e}")

    with st.container(border=True):
        st.caption("Display / Title")
        showContour = st.checkbox("顯示 contour", value=True, key="showContour")
        contourStyle = st.selectbox(
            "contour style",
            ["filled", "lines", "filled + lines", "heatmap"],
            index=0,
            key="contourStyle",
        )
        showContourGrid = st.checkbox("顯示 contour grid", value=False, key="showContourGrid")
        showInfoPanel = st.checkbox("右側顯示參數資訊", value=False, key="showInfoPanel")
        frameLineColor = st.color_picker("frame line color", value="#f4a3a3", key="frameLineColor")
        dieLineColor = st.color_picker("die line color", value="#ececec", key="dieLineColor")
        effectiveEdgeColor = st.color_picker("effective edge color", value="#f4a3a3", key="effectiveEdgeColor")
        waferEdgeColor = st.color_picker("wafer edge color", value="#000000", key="waferEdgeColor")
        contourGridColor = st.color_picker("contour grid color", value="#d9d9d9", key="contourGridColor")
        inputTitle = st.text_input("title", value="wafer_frame_preview", key="inputTitle")

plotDf = pd.DataFrame(columns=["posXMm", "posYMm", "thickness"])
calculatedDf = pd.DataFrame()
duplicateCount = 0
outsideCount = 0
contourGrid = None
hasExcelData = uploadedFile is not None
outputStem = "wafer_frame_preview"
title = inputTitle.strip() if inputTitle.strip() else "wafer_frame_preview"
outputStem = sanitize_file_stem(title)
excelNameForInfo = "(none)"
valueLabel = "thickness"
coordinateMode = "index"
parameterTemplateBytes: bytes | None = None
parameterTemplatePath: Path | None = None
missingParameterColumns = False

if hasExcelData:
    excelNameForInfo = fileName.name

    missingParameterColumns = not hasParameterColumns
    if missingParameterColumns:
        parameterRows = build_parameter_rows(
            stepXUm=stepXUm,
            stepYUm=stepYUm,
            frameOffsetXUm=frameOffsetXUm,
            frameOffsetYUm=frameOffsetYUm,
            arrayX=int(arrayX),
            arrayY=int(arrayY),
            topMm=topMm,
            offsetXUm=offsetXUm,
            offsetYUm=offsetYUm,
            diameterMm=diameterMm,
            flatOption=flatOption,
            edgeExcludeMm=edgeExcludeMm,
            bottomMm=bottomMm,
        )
        selectedSheetWithParameters = build_sheet_with_parameter_columns(rawSheetDf, parameterRows)
        if excelFile is None:
            st.error("Excel 資訊初始化失敗，請重新上傳檔案。")
            st.stop()
        allSheetTables = {
            name: pd.read_excel(io.BytesIO(fileBytes), sheet_name=name, header=None)
            for name in excelFile.sheet_names
        }
        allSheetTables[sheetName] = selectedSheetWithParameters
        parameterTemplateBytes = build_excel_bytes(allSheetTables)
        parameterTemplatePath = Path.cwd() / f"{fileName.stem}_with_params.xlsx"
        parameterTemplatePath.write_bytes(parameterTemplateBytes)

    try:
        sourceDf, valueLabel, coordinateMode = parse_measurement_table(rawSheetDf)
    except Exception as exc:  # pragma: no cover - streamlit runtime feedback
        st.error(f"資料格式錯誤: {exc}")
        st.stop()

    calculatedDf = calculate_positions(
        sourceDf,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        offsetXUm=offsetXUm,
        offsetYUm=offsetYUm,
        coordinateMode=coordinateMode,
        indexBaseYUm=(topMm - edgeExcludeMm) * 1000.0,
    )
    plotDf, duplicateCount = collapse_duplicate_points(calculatedDf)
else:
    pass

try:
    validate_parameters(stepXUm, stepYUm, offsetXUm, offsetYUm, diameterMm)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

waferOutline = build_wafer_outline(diameterMm=diameterMm, flatOption=flatOption)
effectiveOutline = build_effective_outline(waferOutline=waferOutline, edgeExcludeMm=edgeExcludeMm)
if len(effectiveOutline) < 3:
    st.error("edge exclude 太大，已無可用 wafer 區域。請調小 edge exclude。")
    st.stop()

centerReferenceX = (float(waferOutline[:, 0].min()) + float(waferOutline[:, 0].max())) / 2.0
topReferenceY = top_y_at_x(waferOutline, centerReferenceX)
bottomReferenceY = float(waferOutline[:, 1].min())

completeFrames = build_complete_frame_rectangles(
    outline=effectiveOutline,
    stepXUm=stepXUm,
    stepYUm=stepYUm,
    frameOffsetXUm=frameOffsetXUm,
    frameOffsetYUm=frameOffsetYUm,
    topMm=topMm,
    bottomMm=bottomMm,
    topReferenceY=topReferenceY,
    bottomReferenceY=bottomReferenceY,
)
totalFrames = len(completeFrames)
completeDies = build_complete_die_rectangles(
    outline=effectiveOutline,
    stepXUm=stepXUm,
    stepYUm=stepYUm,
    arrayX=int(arrayX),
    arrayY=int(arrayY),
    frameOffsetXUm=frameOffsetXUm,
    frameOffsetYUm=frameOffsetYUm,
    topMm=topMm,
    topReferenceY=topReferenceY,
)
totalDies = len(completeDies)
frameBottomGapMm = min((frame[1] for frame in completeFrames), default=float("nan")) - float(
    waferOutline[:, 1].min()
)
if totalFrames == 0:
    frameBottomGapMm = -1.0

if hasExcelData:
    outsideCount = count_points_outside_outline(plotDf, effectiveOutline)
    if showContour:
        contourGrid = build_interpolated_grid(plotDf, effectiveOutline)

showContourEffective = showContour and hasExcelData

coordinateModeText = (
    "已偵測到浮點座標：前兩欄視為 mm 絕對座標（wafer center = 0,0）。"
    if coordinateMode == "mm"
    else "已偵測到整數座標：前兩欄視為 site index，使用 step/offset 計算位置。"
)

infoPanelText = build_info_panel_text(
    stepXUm=stepXUm,
    stepYUm=stepYUm,
    arrayX=int(arrayX),
    arrayY=int(arrayY),
    frameOffsetXUm=frameOffsetXUm,
    frameOffsetYUm=frameOffsetYUm,
    topMm=topMm,
    bottomMm=bottomMm,
    totalFrames=totalFrames,
    totalDies=totalDies,
    frameBottomGapMm=frameBottomGapMm,
    offsetXUm=offsetXUm,
    offsetYUm=offsetYUm,
    diameterMm=diameterMm,
    flatOption=flatOption,
    edgeExcludeMm=edgeExcludeMm,
    showContour=showContourEffective,
    contourStyle=contourStyle,
    showContourGrid=showContourGrid,
    coordinateMode=coordinateMode,
    valueLabel=valueLabel,
    title=title,
    excelName=excelNameForInfo,
)

figure = render_figure(
    plotDf,
    waferOutline,
    effectiveOutline,
    title,
    contourGrid,
    valueLabel=valueLabel,
    stepXUm=stepXUm,
    stepYUm=stepYUm,
    arrayX=int(arrayX),
    arrayY=int(arrayY),
    frameOffsetXUm=frameOffsetXUm,
    frameOffsetYUm=frameOffsetYUm,
    topMm=topMm,
    bottomMm=bottomMm,
    topReferenceY=topReferenceY,
    bottomReferenceY=bottomReferenceY,
    showContour=showContourEffective,
    contourStyle=contourStyle,
    showContourGrid=showContourGrid,
    showInfoPanel=showInfoPanel,
    infoPanelText=infoPanelText,
    signatureText=f"by cnwang {version}",
    frameLineColor=frameLineColor,
    dieLineColor=dieLineColor,
    effectiveEdgeColor=effectiveEdgeColor,
    waferEdgeColor=waferEdgeColor,
    contourGridColor=contourGridColor,
    showLaserMark=showLaserMark,
    edgeToMarkTopMm=laserMarkEdgeToTopMm,
    charHeightMm=laserMarkCharHeightMm,
    markerLengthMm=laserMarkLengthMm,
    laserMarkPositionDeg=laserMarkPositionDeg,
)
jpgBytes = figure_to_jpg_bytes(figure)
outputPath = Path.cwd() / f"{outputStem}.jpg"
outputPath.write_bytes(jpgBytes)

colChart, colData = st.columns([1.4, 1.0])

with colChart:
    tab1, tab2 = st.tabs(["Wafer Map", "Special View"])
    
    with tab1:
        st.pyplot(figure, width="stretch")
        st.download_button(
            label="下載 JPG",
            data=jpgBytes,
            file_name=f"{outputStem}.jpg",
            mime="image/jpeg",
        )
        st.success(f"JPG 已輸出為 {outputPath.name}")
        if not hasExcelData:
            st.info("未上傳 Excel，僅使用 step/offset 參數顯示 wafer frames。")
        if showContour and not hasExcelData:
            st.caption("未提供 Excel，contour 已自動關閉。")
        if hasExcelData:
            st.caption(f"已上傳 Excel，title 使用左側輸入: {title}")
            st.caption(coordinateModeText)
            if missingParameterColumns and parameterTemplateBytes and parameterTemplatePath:
                st.info("此 Excel 缺少 col4/col5 參數區，已自動產生可回用版本。")
                st.download_button(
                    label="下載回填參數 Excel",
                    data=parameterTemplateBytes,
                    file_name=parameterTemplatePath.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.caption(f"也已輸出檔案：{parameterTemplatePath.name}")
        if duplicateCount:
            st.warning(
                f"偵測到 {duplicateCount} 筆重複座標，繪圖時已先對相同座標的 thickness 取平均。"
            )
        if outsideCount:
            st.warning(f"有 {outsideCount} 個量測點落在 wafer 外框之外，請確認 step/offset 或來源資料。")
        if showContourEffective and contourGrid is None:
            st.warning("可用點位不足以建立平滑 contour，將只顯示量測點與 thickness 標註。")
        if flatOption in {"notch-180", "notch-135"}:
            st.caption(f"{flatOption} 外框使用 6 mm 寬、2 mm 深的近似 V-notch。")
    
    with tab2:
        if isKGDmapFormat and kgdmapData is not None:
            render_kgdmap_viewer(kgdmapData)
        else:
            st.info("Special View tab - 上傳 KGDmap (CSV with Lot column) 或其他特殊格式檔案來顯示內容")

with colData:
    st.subheader("計算結果")
    if hasExcelData:
        displayDf = calculatedDf[
            ["siteX", "siteY", "thickness", "posXUm", "posYUm", "posXMm", "posYMm"]
        ].rename(columns={"thickness": valueLabel})
        if coordinateMode == "mm":
            displayDf = displayDf.rename(columns={"siteX": "coordX(mm)", "siteY": "coordY(mm)"})
        st.dataframe(
            displayDf,
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("未提供 Excel，無量測資料表可顯示。")

plt.close(figure)
