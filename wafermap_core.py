from __future__ import annotations

import io
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from scipy.ndimage import distance_transform_edt
from scipy.interpolate import griddata


defaultDiameterMm = 150.0
flatOptions = {
    "47.5 mm": 47.5,
    "57.5 mm": 57.5,
    "notch": "notch",
}
notchWidthMm = 6.0
notchDepthMm = 2.0


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalizedColumns = {col: col.strip().lower() for col in df.columns}
    renamedDf = df.rename(columns=normalizedColumns)
    required = {"sitex", "sitey", "thickness"}
    missing = required - set(renamedDf.columns)
    if missing:
        missingText = ", ".join(sorted(missing))
        raise ValueError(
            f"Excel 缺少必要欄位: {missingText}。需要包含 siteX, siteY, thickness。"
        )

    return renamedDf[["sitex", "sitey", "thickness"]].rename(
        columns={"sitex": "siteX", "sitey": "siteY"}
    )


def validate_parameters(
    stepXUm: float,
    stepYUm: float,
    offsetXUm: float,
    offsetYUm: float,
    diameterMm: float,
) -> None:
    if stepXUm <= 0 or stepYUm <= 0:
        raise ValueError("stepX 與 stepY 必須大於 0。")
    if offsetXUm <= -stepXUm or offsetXUm >= stepXUm:
        raise ValueError("offsetX 建議範圍為 (-stepX, stepX)。")
    if offsetYUm <= -stepYUm or offsetYUm >= stepYUm:
        raise ValueError("offsetY 建議範圍為 (-stepY, stepY)。")
    if diameterMm <= 0:
        raise ValueError("wafer diameter 必須大於 0。")


def build_wafer_outline(diameterMm: float, flatOption: str) -> np.ndarray:
    radius = diameterMm / 2.0

    if flatOption == "notch":
        halfWidth = notchWidthMm / 2.0
        yJoin = -math.sqrt(max(radius**2 - halfWidth**2, 0.0))
        thetaLeft = math.atan2(yJoin, -halfWidth)
        thetaRight = math.atan2(yJoin, halfWidth)
        arcAngles = np.linspace(thetaRight, thetaLeft + 2.0 * math.pi, 720)
        arc = np.column_stack((radius * np.cos(arcAngles), radius * np.sin(arcAngles)))
        notch = np.array(
            [
                [-halfWidth, yJoin],
                [0.0, -radius + notchDepthMm],
                [halfWidth, yJoin],
            ]
        )
        return np.vstack((arc, notch, arc[0]))

    flatLength = flatOptions[flatOption]
    halfFlat = float(flatLength) / 2.0
    yFlat = -math.sqrt(max(radius**2 - halfFlat**2, 0.0))
    thetaLeft = math.atan2(yFlat, -halfFlat)
    thetaRight = math.atan2(yFlat, halfFlat)
    arcAngles = np.linspace(thetaRight, thetaLeft + 2.0 * math.pi, 720)
    arc = np.column_stack((radius * np.cos(arcAngles), radius * np.sin(arcAngles)))
    flat = np.array([[-halfFlat, yFlat], [halfFlat, yFlat]])
    return np.vstack((arc, flat, arc[0]))


def polygon_area(points: np.ndarray) -> float:
    if len(points) < 3:
        return 0.0
    xValues = points[:, 0]
    yValues = points[:, 1]
    return 0.5 * np.sum(xValues * np.roll(yValues, -1) - yValues * np.roll(xValues, -1))


def build_effective_outline(
    waferOutline: np.ndarray,
    edgeExcludeMm: float,
    gridSize: int = 900,
) -> np.ndarray:
    if edgeExcludeMm <= 0:
        return waferOutline.copy()

    xMin, yMin = waferOutline.min(axis=0)
    xMax, yMax = waferOutline.max(axis=0)
    xValues = np.linspace(xMin, xMax, gridSize)
    yValues = np.linspace(yMin, yMax, gridSize)
    gridX, gridY = np.meshgrid(xValues, yValues)

    outlinePath = MplPath(waferOutline)
    maskInside = outlinePath.contains_points(
        np.column_stack((gridX.ravel(), gridY.ravel()))
    ).reshape(gridX.shape)
    if not np.any(maskInside):
        return np.empty((0, 2))

    xStep = (xMax - xMin) / max(gridSize - 1, 1)
    yStep = (yMax - yMin) / max(gridSize - 1, 1)
    distanceInside = distance_transform_edt(maskInside, sampling=(yStep, xStep))
    if float(distanceInside.max()) <= edgeExcludeMm:
        return np.empty((0, 2))

    contourFigure, contourAxis = plt.subplots(figsize=(4, 4), dpi=100)
    contourSet = contourAxis.contour(xValues, yValues, distanceInside, levels=[edgeExcludeMm])
    contourSegments = contourSet.allsegs[0] if contourSet.allsegs else []
    plt.close(contourFigure)

    if not contourSegments:
        return np.empty((0, 2))

    bestSegment = max(contourSegments, key=lambda segment: abs(polygon_area(segment)))
    if len(bestSegment) < 3:
        return np.empty((0, 2))
    if not np.allclose(bestSegment[0], bestSegment[-1]):
        bestSegment = np.vstack((bestSegment, bestSegment[0]))
    return bestSegment


def calculate_positions(
    df: pd.DataFrame,
    stepXUm: float,
    stepYUm: float,
    offsetXUm: float,
    offsetYUm: float,
    coordinateMode: str = "index",
    indexBaseYUm: float = 0.0,
) -> pd.DataFrame:
    result = df.copy()
    if coordinateMode == "mm":
        result["posXMm"] = result["siteX"]
        result["posYMm"] = result["siteY"]
        result["posXUm"] = result["posXMm"] * 1000.0
        result["posYUm"] = result["posYMm"] * 1000.0
    else:
        siteXIndex = result["siteX"].astype(float)
        siteYIndex = result["siteY"].astype(float)

        # Auto-detect 1-based integer site indexing and convert to 0-based.
        if ((siteXIndex - np.round(siteXIndex)).abs() < 1e-9).all() and float(siteXIndex.min()) >= 1.0:
            siteXIndex = siteXIndex - 1.0
        if ((siteYIndex - np.round(siteYIndex)).abs() < 1e-9).all() and float(siteYIndex.min()) >= 1.0:
            siteYIndex = siteYIndex - 1.0

        result["posXUm"] = siteXIndex * stepXUm + offsetXUm - (stepXUm / 2.0)
        result["posYUm"] = siteYIndex * stepYUm + offsetYUm + indexBaseYUm
        result["posXMm"] = result["posXUm"] / 1000.0
        result["posYMm"] = result["posYUm"] / 1000.0
    return result


def collapse_duplicate_points(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    duplicateCount = int(
        df.duplicated(subset=["posXMm", "posYMm"], keep=False).sum()
    )
    groupedDf = (
        df.groupby(["posXMm", "posYMm"], as_index=False)
        .agg(
            thickness=("thickness", "mean"),
            posXUm=("posXUm", "first"),
            posYUm=("posYUm", "first"),
        )
        .sort_values(["posYMm", "posXMm"])
        .reset_index(drop=True)
    )
    return groupedDf, duplicateCount


def count_points_outside_outline(pointsDf: pd.DataFrame, outline: np.ndarray) -> int:
    outlinePath = MplPath(outline)
    points = pointsDf[["posXMm", "posYMm"]].to_numpy(dtype=float)
    inside = outlinePath.contains_points(points)
    return int((~inside).sum())


def build_interpolated_grid(
    pointsDf: pd.DataFrame,
    outline: np.ndarray,
    gridSize: int = 320,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    points = pointsDf[["posXMm", "posYMm"]].to_numpy(dtype=float)
    values = pointsDf["thickness"].to_numpy(dtype=float)
    if len(points) < 3:
        return None

    centered = points - points.mean(axis=0, keepdims=True)
    if np.linalg.matrix_rank(centered) < 2:
        return None

    xMin, yMin = outline.min(axis=0)
    xMax, yMax = outline.max(axis=0)
    gridX, gridY = np.meshgrid(
        np.linspace(xMin, xMax, gridSize),
        np.linspace(yMin, yMax, gridSize),
    )

    linearGrid = griddata(points, values, (gridX, gridY), method="linear")
    nearestGrid = griddata(points, values, (gridX, gridY), method="nearest")
    gridZ = np.where(np.isnan(linearGrid), nearestGrid, linearGrid)

    outlinePath = MplPath(outline)
    inside = outlinePath.contains_points(
        np.column_stack((gridX.ravel(), gridY.ravel()))
    ).reshape(gridX.shape)
    gridZ = np.where(inside, gridZ, np.nan)
    return gridX, gridY, gridZ


def build_frame_origins(
    axisMin: float,
    axisMax: float,
    pitchMm: float,
    offsetMm: float,
) -> np.ndarray:
    if pitchMm <= 0:
        return np.array([])

    firstIndex = math.floor((axisMin - offsetMm) / pitchMm) - 1
    lastIndex = math.ceil((axisMax - offsetMm) / pitchMm) + 1
    frameIndexes = np.arange(firstIndex, lastIndex + 1)
    return offsetMm + frameIndexes * pitchMm


def build_frame_y_origins_from_top(
    yMin: float,
    yMax: float,
    pitchMm: float,
    topMm: float,
    offsetYMm: float,
    bottomMm: float,
    topReferenceY: float,
    bottomReferenceY: float,
) -> np.ndarray:
    if pitchMm <= 0:
        return np.array([])

    topEdgeStart = topReferenceY - topMm - offsetYMm
    maxRows = int(math.ceil((yMax - yMin + topMm + abs(offsetYMm)) / pitchMm)) + 8
    yOrigins: list[float] = []

    for rowIndex in range(maxRows):
        yTop = topEdgeStart - rowIndex * pitchMm
        yOrigin = yTop - pitchMm
        if yOrigin > yMax:
            continue
        if yOrigin < bottomReferenceY + bottomMm:
            break
        if yTop < yMin:
            break
        yOrigins.append(yOrigin)

    return np.array(yOrigins)


def top_y_at_x(outline: np.ndarray, xRef: float) -> float:
    intersections: list[float] = []

    for index in range(len(outline) - 1):
        pointA = outline[index]
        pointB = outline[index + 1]
        xA, yA = float(pointA[0]), float(pointA[1])
        xB, yB = float(pointB[0]), float(pointB[1])

        if abs(xA - xB) <= 1e-12:
            if abs(xRef - xA) <= 1e-9:
                intersections.append(max(yA, yB))
            continue

        t = (xRef - xA) / (xB - xA)
        if 0.0 <= t <= 1.0:
            yIntersect = yA + t * (yB - yA)
            intersections.append(float(yIntersect))

    if intersections:
        return max(intersections)

    nearestIndex = int(np.argmin(np.abs(outline[:, 0] - xRef)))
    fallbackY = float(outline[nearestIndex, 1])
    return max(fallbackY, float(np.max(outline[:, 1])))


def build_frame_edge_samples(
    xOrigin: float,
    yOrigin: float,
    stepXMm: float,
    stepYMm: float,
    samplesPerEdge: int = 7,
) -> np.ndarray:
    tValues = np.linspace(0.0, 1.0, samplesPerEdge)
    xRight = xOrigin + stepXMm
    yTop = yOrigin + stepYMm
    bottom = np.column_stack((xOrigin + tValues * stepXMm, np.full_like(tValues, yOrigin)))
    right = np.column_stack((np.full_like(tValues, xRight), yOrigin + tValues * stepYMm))
    top = np.column_stack((xRight - tValues * stepXMm, np.full_like(tValues, yTop)))
    left = np.column_stack((np.full_like(tValues, xOrigin), yTop - tValues * stepYMm))
    return np.vstack((bottom, right, top, left))


def is_complete_frame_inside(
    outlinePath: MplPath,
    xOrigin: float,
    yOrigin: float,
    stepXMm: float,
    stepYMm: float,
) -> bool:
    edgeSamples = build_frame_edge_samples(xOrigin, yOrigin, stepXMm, stepYMm)
    inside = outlinePath.contains_points(edgeSamples, radius=1e-9)
    return bool(np.all(inside))


def canonical_edge_key(
    pointA: tuple[float, float],
    pointB: tuple[float, float],
    decimals: int = 6,
) -> tuple[tuple[float, float], tuple[float, float]]:
    roundedA = (round(float(pointA[0]), decimals), round(float(pointA[1]), decimals))
    roundedB = (round(float(pointB[0]), decimals), round(float(pointB[1]), decimals))
    return (roundedA, roundedB) if roundedA <= roundedB else (roundedB, roundedA)


def draw_frames(
    ax: plt.Axes,
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    bottomMm: float,
    topReferenceY: float,
    bottomReferenceY: float,
    lineColor: str,
) -> None:
    completeFrames = build_complete_frame_rectangles(
        outline=outline,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        frameOffsetXUm=frameOffsetXUm,
        frameOffsetYUm=frameOffsetYUm,
        topMm=topMm,
        bottomMm=bottomMm,
        topReferenceY=topReferenceY,
        bottomReferenceY=bottomReferenceY,
    )
    frameEdges: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for xOrigin, yOrigin, xRight, yTop in completeFrames:
        corners = [
            (xOrigin, yOrigin),
            (xRight, yOrigin),
            (xRight, yTop),
            (xOrigin, yTop),
        ]
        for index in range(4):
            pointA = corners[index]
            pointB = corners[(index + 1) % 4]
            frameEdges.add(canonical_edge_key(pointA, pointB))

    for pointA, pointB in sorted(frameEdges):
        ax.plot(
            [pointA[0], pointB[0]],
            [pointA[1], pointB[1]],
            color=lineColor,
            linewidth=0.9,
            linestyle=(0, (4, 4)),
            alpha=0.9,
            zorder=2,
        )


def draw_dies(
    ax: plt.Axes,
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    arrayX: int,
    arrayY: int,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    topReferenceY: float,
    lineColor: str,
) -> None:
    completeDies = build_complete_die_rectangles(
        outline=outline,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        arrayX=arrayX,
        arrayY=arrayY,
        frameOffsetXUm=frameOffsetXUm,
        frameOffsetYUm=frameOffsetYUm,
        topMm=topMm,
        topReferenceY=topReferenceY,
    )
    dieEdges: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for xOrigin, yOrigin, xRight, yTop in completeDies:
        corners = [
            (xOrigin, yOrigin),
            (xRight, yOrigin),
            (xRight, yTop),
            (xOrigin, yTop),
        ]
        for index in range(4):
            pointA = corners[index]
            pointB = corners[(index + 1) % 4]
            dieEdges.add(canonical_edge_key(pointA, pointB))

    for pointA, pointB in sorted(dieEdges):
        ax.plot(
            [pointA[0], pointB[0]],
            [pointA[1], pointB[1]],
            color=lineColor,
            linewidth=0.6,
            linestyle="-",
            alpha=1.0,
            zorder=1.6,
        )


def build_complete_rectangles(
    outline: np.ndarray,
    tileWidthMm: float,
    tileHeightMm: float,
    offsetXMm: float,
    offsetYMm: float,
    topMm: float,
    bottomMm: float,
    topReferenceY: float | None = None,
    bottomReferenceY: float | None = None,
    alignCenterX: bool = True,
) -> list[tuple[float, float, float, float]]:
    if tileWidthMm <= 0 or tileHeightMm <= 0:
        return []

    xMin, yMin = outline.min(axis=0)
    xMax, yMax = outline.max(axis=0)
    if topReferenceY is None:
        centerX = (xMin + xMax) / 2.0
        topReferenceY = top_y_at_x(outline, centerX)
    if bottomReferenceY is None:
        bottomReferenceY = yMin
    outlinePath = MplPath(outline)

    xGridOffset = offsetXMm - (tileWidthMm / 2.0 if alignCenterX else 0.0)
    xOrigins = build_frame_origins(xMin, xMax, tileWidthMm, xGridOffset)
    yOrigins = build_frame_y_origins_from_top(
        yMin=yMin,
        yMax=yMax,
        pitchMm=tileHeightMm,
        topMm=topMm,
        offsetYMm=offsetYMm,
        bottomMm=bottomMm,
        topReferenceY=topReferenceY,
        bottomReferenceY=bottomReferenceY,
    )
    completeRects: list[tuple[float, float, float, float]] = []

    for xOrigin in xOrigins:
        xRight = xOrigin + tileWidthMm
        if xRight < xMin or xOrigin > xMax:
            continue

        for yOrigin in yOrigins:
            yTop = yOrigin + tileHeightMm
            if yTop < yMin or yOrigin > yMax:
                continue
            if not is_complete_frame_inside(outlinePath, xOrigin, yOrigin, tileWidthMm, tileHeightMm):
                continue
            completeRects.append((xOrigin, yOrigin, xRight, yTop))

    return completeRects


def build_complete_frame_rectangles(
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    bottomMm: float,
    topReferenceY: float,
    bottomReferenceY: float,
) -> list[tuple[float, float, float, float]]:
    stepXMm = stepXUm / 1000.0
    stepYMm = stepYUm / 1000.0
    frameOffsetXMm = frameOffsetXUm / 1000.0
    frameOffsetYMm = frameOffsetYUm / 1000.0
    return build_complete_rectangles(
        outline=outline,
        tileWidthMm=stepXMm,
        tileHeightMm=stepYMm,
        offsetXMm=frameOffsetXMm,
        offsetYMm=frameOffsetYMm,
        topMm=topMm,
        bottomMm=bottomMm,
        topReferenceY=topReferenceY,
        bottomReferenceY=bottomReferenceY,
        alignCenterX=True,
    )


def build_complete_die_rectangles(
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    arrayX: int,
    arrayY: int,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    topReferenceY: float,
) -> list[tuple[float, float, float, float]]:
    safeArrayX = max(int(arrayX), 1)
    safeArrayY = max(int(arrayY), 1)
    dieWidthMm = (stepXUm / 1000.0) / safeArrayX
    dieHeightMm = (stepYUm / 1000.0) / safeArrayY
    frameOffsetXMm = frameOffsetXUm / 1000.0
    frameOffsetYMm = frameOffsetYUm / 1000.0
    return build_complete_rectangles(
        outline=outline,
        tileWidthMm=dieWidthMm,
        tileHeightMm=dieHeightMm,
        offsetXMm=frameOffsetXMm,
        offsetYMm=frameOffsetYMm,
        topMm=topMm,
        bottomMm=0.0,
        topReferenceY=topReferenceY,
        bottomReferenceY=float(outline[:, 1].min()),
        alignCenterX=True,
    )


def count_complete_frames(
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    bottomMm: float,
    topReferenceY: float,
    bottomReferenceY: float,
) -> int:
    completeFrames = build_complete_frame_rectangles(
        outline=outline,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        frameOffsetXUm=frameOffsetXUm,
        frameOffsetYUm=frameOffsetYUm,
        topMm=topMm,
        bottomMm=bottomMm,
        topReferenceY=topReferenceY,
        bottomReferenceY=bottomReferenceY,
    )
    return len(completeFrames)


def render_figure(
    pointsDf: pd.DataFrame,
    waferOutline: np.ndarray,
    effectiveOutline: np.ndarray,
    title: str,
    contourGrid: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
    valueLabel: str,
    stepXUm: float,
    stepYUm: float,
    arrayX: int,
    arrayY: int,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    topMm: float,
    bottomMm: float,
    topReferenceY: float,
    bottomReferenceY: float,
    showContour: bool,
    contourStyle: str,
    showContourGrid: bool,
    showInfoPanel: bool,
    infoPanelText: str,
    signatureText: str,
    frameLineColor: str,
    dieLineColor: str,
    effectiveEdgeColor: str,
    waferEdgeColor: str,
    contourGridColor: str,
) -> plt.Figure:
    radius = np.max(np.linalg.norm(waferOutline, axis=1))
    hasPoints = not pointsDf.empty
    canRenderContour = showContour and contourGrid is not None
    figureWidth = 10.8 if showInfoPanel else 8.0
    fig, ax = plt.subplots(figsize=(figureWidth, 8), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f8fbff")
    if showInfoPanel:
        fig.subplots_adjust(right=0.74)

    def add_thickness_colorbar(mappable) -> None:
        colorbar = fig.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label(valueLabel)

    if canRenderContour:
        gridX, gridY, gridZ = contourGrid
        contourMappable = None
        if contourStyle == "lines":
            contourMappable = ax.contour(
                gridX,
                gridY,
                gridZ,
                levels=14,
                cmap="viridis",
                linewidths=1.0,
                alpha=0.95,
            )
        elif contourStyle == "filled + lines":
            contourMappable = ax.contourf(
                gridX,
                gridY,
                gridZ,
                levels=18,
                cmap="viridis",
                alpha=0.86,
            )
            ax.contour(
                gridX,
                gridY,
                gridZ,
                levels=14,
                colors="#2a2a2a",
                linewidths=0.55,
                alpha=0.55,
            )
        elif contourStyle == "heatmap":
            contourMappable = ax.imshow(
                gridZ,
                extent=(float(np.nanmin(gridX)), float(np.nanmax(gridX)), float(np.nanmin(gridY)), float(np.nanmax(gridY))),
                origin="lower",
                cmap="viridis",
                alpha=0.88,
                interpolation="bilinear",
            )
        else:
            contourMappable = ax.contourf(
                gridX,
                gridY,
                gridZ,
                levels=18,
                cmap="viridis",
                alpha=0.88,
            )
        add_thickness_colorbar(contourMappable)

    if hasPoints:
        scatter = ax.scatter(
            pointsDf["posXMm"],
            pointsDf["posYMm"],
            c=pointsDf["thickness"],
            cmap="viridis",
            s=46,
            edgecolors="black",
            linewidths=0.6,
            zorder=3,
        )

        if not canRenderContour:
            add_thickness_colorbar(scatter)

    draw_dies(
        ax,
        effectiveOutline,
        stepXUm,
        stepYUm,
        arrayX,
        arrayY,
        frameOffsetXUm,
        frameOffsetYUm,
        topMm,
        topReferenceY,
        dieLineColor,
    )
    draw_frames(
        ax,
        effectiveOutline,
        stepXUm,
        stepYUm,
        frameOffsetXUm,
        frameOffsetYUm,
        topMm,
        bottomMm,
        topReferenceY,
        bottomReferenceY,
        frameLineColor,
    )
    ax.plot(waferOutline[:, 0], waferOutline[:, 1], color=waferEdgeColor, linewidth=2.0, zorder=4)
    if len(effectiveOutline) > 2:
        ax.plot(
            effectiveOutline[:, 0],
            effectiveOutline[:, 1],
            color=effectiveEdgeColor,
            linewidth=1.4,
            zorder=4,
        )

    if hasPoints:
        for row in pointsDf.itertuples():
            ax.annotate(
                f"{row.thickness:.1f}",
                (row.posXMm, row.posYMm),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
                color="#1a1a1a",
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.7},
            )

    margin = max(radius * 0.06, 5.0)
    ax.set_xlim(waferOutline[:, 0].min() - margin, waferOutline[:, 0].max() + margin)
    ax.set_ylim(waferOutline[:, 1].min() - margin, waferOutline[:, 1].max() + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(title)
    if showContourGrid:
        ax.grid(True, color=contourGridColor, linestyle="--", linewidth=0.6, alpha=0.9)
    else:
        ax.grid(False)

    if showInfoPanel and infoPanelText:
        fig.text(
            0.77,
            0.50,
            infoPanelText,
            ha="left",
            va="center",
            fontsize=8.8,
            color="#2f2f2f",
            linespacing=1.35,
            bbox={
                "boxstyle": "round,pad=0.35",
                "fc": "white",
                "ec": "#c9c9c9",
                "alpha": 0.95,
            },
            clip_on=False,
        )

    if signatureText:
        fig.text(
            0.99,
            0.008,
            signatureText,
            ha="right",
            va="bottom",
            fontsize=8.5,
            color="#bdbdbd",
        )
    return fig


def figure_to_jpg_bytes(fig: plt.Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="jpg", dpi=300, bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    return buffer.getvalue()
