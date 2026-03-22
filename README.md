# waferMap

A Streamlit app for plotting wafer thickness contour maps from Excel measurement data.

by cnwang, 2026/03


## Features

- Excel upload is optional
- No Excel: render wafer outline + frame-only preview
- With Excel: render points and optional contour
- Input wafer map parameters: `stepX`, `stepY`, `offsetX`, `offsetY`, `frame offset X`, `frame offset Y`, `wafer diameter`, `flat`
- Convert site coordinates into absolute wafer coordinates
- Draw wafer outline with `47.5 mm`, `57.5 mm`, or `notch`
- Draw frame lines (light red dashed) using `stepX`/`stepY` and frame offsets
- Toggle contour display
- Render measurement point labels when Excel data exists
- Toggle contour grid display (hidden by default, light gray when shown)
- Export chart as `.jpg`
- With Excel: output filename follows uploaded Excel base name
- Without Excel: output filename is `wafer_frame_preview.jpg`

## Input Data (Optional)

If you upload Excel, it must contain these columns:

| Column | Description | Unit |
| --- | --- | --- |
| `siteX` | Site X index | count |
| `siteY` | Site Y index | count |
| `thickness` | Measured thickness | A |

## Parameters

| Parameter | Description | Unit |
| --- | --- | --- |
| `stepX` | Frame width | um |
| `stepY` | Frame height | um |
| `offsetX` | X offset from frame lower-left origin | um |
| `offsetY` | Y offset from frame lower-left origin | um |
| `frame offset X` | Frame grid X offset | um |
| `frame offset Y` | Frame grid Y offset | um |
| `wafer diameter` | Wafer diameter | mm |
| `flat` | Wafer edge type: `47.5 mm`, `57.5 mm`, `notch` | mm / type |
| `show contour` | Show/hide contour (only effective when Excel is uploaded) | bool |
| `show contour grid` | Show/hide contour grid (default hidden) | bool |

Rules:

- `offsetX < stepX`
- `offsetY < stepY`
- default wafer diameter is `150 mm`

Position calculation:

```text
posX = siteX * stepX + offsetX
posY = siteY * stepY + offsetY
```

The app converts `posX` and `posY` from `um` to `mm` for plotting around wafer center `(0, 0)`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Output

- Interactive Streamlit view of wafer frames (always)
- Contour and thickness labels when Excel data is uploaded
- A `.jpg` file saved in the working directory
- A download button in the Streamlit UI for the generated image

## Files

- `app.py`: Streamlit UI
- `wafermap_core.py`: calculation and plotting logic
- `requirements.txt`: Python dependencies

## Notes

- `thickness` uses unit `A`
- `stepX`, `stepY`, `offsetX`, `offsetY`, `frame offset X`, `frame offset Y` use unit `um`
- `wafer diameter` and flat size use unit `mm`
- `notch` is currently drawn as an approximate V-notch
- frame lines are light red dashed lines clipped inside wafer outline
- contour grid is optional and shown in light gray when enabled
