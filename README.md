# waferMap

A Streamlit app for plotting wafer thickness contour maps from Excel measurement data.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.55-FF4B4B.svg)](https://streamlit.io/)
[![Pandas](https://img.shields.io/badge/pandas-2.3-150458.svg)](https://pandas.pydata.org/)
[![Matplotlib](https://img.shields.io/badge/matplotlib-3.10-11557c.svg)](https://matplotlib.org/)
[![SciPy](https://img.shields.io/badge/scipy-1.17-8CAAE6.svg)](https://scipy.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

by cnwang, 2026/03


## Features

- Excel upload is optional
- No Excel: render wafer outline + frame-only preview
- With Excel: render points and optional contour
- Sidebar parameters are arranged in 4 boxed sections
- Input wafer map parameters: `stepX`, `stepY`, `top`, `frame offset X`, `frame offset Y`, `offsetX`, `offsetY`, `wafer diameter`, `flat`, `edge exclude`
- Convert site coordinates into absolute wafer coordinates
- Draw wafer outline with `47.5 mm`, `57.5 mm`, or `notch`
- Draw an inner effective wafer boundary using `edge exclude` (light red line)
- Draw frame lines (light red dashed) using `stepX`/`stepY` and frame offsets
- Frame vertical placement starts from wafer top minus `top`, then arranged downward
- Show only complete rectangular frames fully inside wafer; partial frame segments are hidden
- Toggle contour display
- Render measurement point labels when Excel data exists
- Toggle contour grid display (hidden by default, light gray when shown)
- Optional info panel on the right side of wafer chart
- Info panel includes `total frames` (count of complete frames)
- Info panel includes `edge exclude`, `top`, and `frame bottom gap` (mm)
- Bottom-edge signature text: `by cnwang {VERSION}`
- Title input supported; when Excel is uploaded, title automatically uses Excel filename
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
| `top` | Start frame placement from wafer top minus this value | mm |
| `frame offset X` | Frame grid X offset | um |
| `frame offset Y` | Frame grid Y offset | um |
| `offsetX` | Site offset X from frame lower-left origin | um |
| `offsetY` | Site offset Y from frame lower-left origin | um |
| `wafer diameter` | Wafer diameter | mm |
| `flat` | Wafer edge type: `47.5 mm`, `57.5 mm`, `notch` (default `57.5 mm`) | mm / type |
| `edge exclude` | Inward shrink distance from original wafer edge (default `2.5`) | mm |
| `show contour` | Show/hide contour (only effective when Excel is uploaded) | bool |
| `show contour grid` | Show/hide contour grid (default hidden) | bool |
| `show info panel` | Show/hide parameter summary text at chart right side | bool |
| `title` | Custom chart title (overridden by Excel filename when Excel is uploaded) | text |

Rules:

- `offsetX < stepX`
- `offsetY < stepY`
- default wafer diameter is `150 mm`
- default `top` is `10 mm`
- default `edge exclude` is `2.5 mm`
- contour range, outside-wafer checks, and complete-frame checks are based on the effective (edge-excluded) wafer boundary

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
- Light red inner boundary shows effective wafer area after `edge exclude`
- A `.jpg` file saved in the working directory
- A download button in the Streamlit UI for the generated image

## Files

- `app.py`: Streamlit UI
- `wafermap_core.py`: calculation and plotting logic
- `requirements.txt`: Python dependencies

## Notes

- `thickness` uses unit `A`
- `stepX`, `stepY`, `offsetX`, `offsetY`, `frame offset X`, `frame offset Y` use unit `um`
- `wafer diameter`, `top`, `edge exclude`, and flat size use unit `mm`
- `notch` is currently drawn as an approximate V-notch
- frame lines are light red dashed lines
- only fully complete rectangular frames are drawn
- `total frames` in info panel counts only complete rectangular frames
- frame vertical placement starts from top and goes downward
- `frame bottom gap` in info panel is the distance from arranged frame bottom edge to effective wafer bottom edge
- contour grid is optional and shown in light gray when enabled
