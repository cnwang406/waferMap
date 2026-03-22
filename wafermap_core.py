from __future__ import annotations

import io
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
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
    if offsetXUm < 0 or offsetYUm < 0:
        raise ValueError("offsetX 與 offsetY 必須大於或等於 0。")
    if offsetXUm >= stepXUm or offsetYUm >= stepYUm:
        raise ValueError("offsetX 必須小於 stepX，且 offsetY 必須小於 stepY。")
    if diameterMm <= 0:
        raise ValueError("wafer diameter 必須大於 0。")


def build_wafer_outline(diameterMm: float, flatOption: str) -> np.ndarray:
    radius = diameterMm / 2.0

    if flatOption == "notch":
        halfWidth = notchWidthMm / 2.0
        yJoin = -math.sqrt(max(radius**2 - halfWidth**2, 0.0))
        thetaLeft = math.atan2(yJoin, -halfWidth)
        thetaRight = math.atan2(yJoin, halfWidth)
        arcAngles = np.linspace(thetaLeft, thetaRight + 2.0 * math.pi, 720)
        arc = np.column_stack((radius * np.cos(arcAngles), radius * np.sin(arcAngles)))
        notch = np.array(
            [
                [halfWidth, yJoin],
                [0.0, -radius + notchDepthMm],
                [-halfWidth, yJoin],
            ]
        )
        return np.vstack((arc, notch, arc[0]))

    flatLength = flatOptions[flatOption]
    halfFlat = float(flatLength) / 2.0
    yFlat = -math.sqrt(max(radius**2 - halfFlat**2, 0.0))
    thetaLeft = math.atan2(yFlat, -halfFlat)
    thetaRight = math.atan2(yFlat, halfFlat)
    arcAngles = np.linspace(thetaLeft, thetaRight + 2.0 * math.pi, 720)
    arc = np.column_stack((radius * np.cos(arcAngles), radius * np.sin(arcAngles)))
    flat = np.array([[halfFlat, yFlat], [-halfFlat, yFlat]])
    return np.vstack((arc, flat, arc[0]))


def calculate_positions(
    df: pd.DataFrame,
    stepXUm: float,
    stepYUm: float,
    offsetXUm: float,
    offsetYUm: float,
) -> pd.DataFrame:
    result = df.copy()
    result["posXUm"] = result["siteX"] * stepXUm + offsetXUm
    result["posYUm"] = result["siteY"] * stepYUm + offsetYUm
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
) -> None:
    completeFrames = build_complete_frame_rectangles(
        outline=outline,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        frameOffsetXUm=frameOffsetXUm,
        frameOffsetYUm=frameOffsetYUm,
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
            color="#f4a3a3",
            linewidth=0.9,
            linestyle=(0, (4, 4)),
            alpha=0.9,
            zorder=2,
        )


def build_complete_frame_rectangles(
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
) -> list[tuple[float, float, float, float]]:
    stepXMm = stepXUm / 1000.0
    stepYMm = stepYUm / 1000.0
    frameOffsetXMm = frameOffsetXUm / 1000.0
    frameOffsetYMm = frameOffsetYUm / 1000.0
    if stepXMm <= 0 or stepYMm <= 0:
        return []

    xMin, yMin = outline.min(axis=0)
    xMax, yMax = outline.max(axis=0)
    outlinePath = MplPath(outline)

    xOrigins = build_frame_origins(xMin, xMax, stepXMm, frameOffsetXMm)
    yOrigins = build_frame_origins(yMin, yMax, stepYMm, frameOffsetYMm)
    completeFrames: list[tuple[float, float, float, float]] = []

    for xOrigin in xOrigins:
        xRight = xOrigin + stepXMm
        if xRight < xMin or xOrigin > xMax:
            continue

        for yOrigin in yOrigins:
            yTop = yOrigin + stepYMm
            if yTop < yMin or yOrigin > yMax:
                continue
            if not is_complete_frame_inside(outlinePath, xOrigin, yOrigin, stepXMm, stepYMm):
                continue

            completeFrames.append((xOrigin, yOrigin, xRight, yTop))

    return completeFrames


def count_complete_frames(
    outline: np.ndarray,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
) -> int:
    completeFrames = build_complete_frame_rectangles(
        outline=outline,
        stepXUm=stepXUm,
        stepYUm=stepYUm,
        frameOffsetXUm=frameOffsetXUm,
        frameOffsetYUm=frameOffsetYUm,
    )
    return len(completeFrames)


def render_figure(
    pointsDf: pd.DataFrame,
    outline: np.ndarray,
    title: str,
    contourGrid: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
    stepXUm: float,
    stepYUm: float,
    frameOffsetXUm: float,
    frameOffsetYUm: float,
    showContour: bool,
    showContourGrid: bool,
    showInfoPanel: bool,
    infoPanelText: str,
    signatureText: str,
) -> plt.Figure:
    radius = np.max(np.linalg.norm(outline, axis=1))
    hasPoints = not pointsDf.empty
    canRenderContour = showContour and contourGrid is not None
    figureWidth = 10.8 if showInfoPanel else 8.0
    fig, ax = plt.subplots(figsize=(figureWidth, 8), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f8fbff")

    if canRenderContour:
        gridX, gridY, gridZ = contourGrid
        contour = ax.contourf(
            gridX,
            gridY,
            gridZ,
            levels=18,
            cmap="viridis",
            alpha=0.88,
        )
        colorbar = fig.colorbar(contour, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label("Thickness (A)")

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
            colorbar = fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
            colorbar.set_label("Thickness (A)")

    draw_frames(ax, outline, stepXUm, stepYUm, frameOffsetXUm, frameOffsetYUm)
    ax.plot(outline[:, 0], outline[:, 1], color="black", linewidth=2.0, zorder=4)

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
    ax.set_xlim(outline[:, 0].min() - margin, outline[:, 0].max() + margin)
    ax.set_ylim(outline[:, 1].min() - margin, outline[:, 1].max() + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(title)
    if showContourGrid:
        ax.grid(True, color="#d9d9d9", linestyle="--", linewidth=0.6, alpha=0.9)
    else:
        ax.grid(False)

    if showInfoPanel and infoPanelText:
        ax.text(
            1.03,
            0.98,
            infoPanelText,
            transform=ax.transAxes,
            ha="left",
            va="top",
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
