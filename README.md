# waferMap

A Streamlit app for plotting wafer thickness contour maps from Excel measurement data.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.55-FF4B4B.svg)](https://streamlit.io/)
[![Pandas](https://img.shields.io/badge/pandas-2.3-150458.svg)](https://pandas.pydata.org/)
[![Matplotlib](https://img.shields.io/badge/matplotlib-3.10-11557c.svg)](https://matplotlib.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

by cnwang, 2026/03


## Features

- Excel upload is optional
- No Excel: render wafer outline + frame-only preview
- With Excel: render points and optional contour
- Sidebar parameters are arranged in 5 boxed sections
- Optional laser mark rectangle overlay with adjustable position, length, height, and edge distance
- Input wafer map parameters: `stepX`, `stepY`, `array X`, `array Y`, `top`, `bottom`, `frame offset X`, `frame offset Y`, `offsetX`, `offsetY`, `wafer diameter`, `flat`, `edge exclude`
- Laser mark parameters: `edge-to-mark_top`, `char-height`, `marker length`, `position`, `enable lasermark frame`
- Convert site coordinates into absolute wafer coordinates
- Draw wafer outline with `47.5 mm`, `57.5 mm`, `notch-180`, or `notch-135`
- For flat wafers, the outer circular edge is clipped by the flat segment (no extra circle shown outside flat)
- Draw an inner effective wafer boundary using `edge exclude` (light red line)
- Draw frame lines (light red dashed) using `stepX`/`stepY` and frame offsets
- Draw die grid lines (lighter gray) using die size `stepX/arrayX` and `stepY/arrayY`
- Draw complete dies in regions between frame area and wafer edge when full die fits
- Frame vertical placement starts from wafer top minus `top`, then arranged downward
- Frame bottom gap constraint: frame lowest edge must keep at least `bottom` distance from wafer bottom
- Show only complete rectangular frames fully inside wafer; partial frame segments are hidden
- Toggle contour display
- Contour interpolation and edge-exclude calculation run without SciPy dependency
- Thickness colorbar and info panel layout are auto-adjusted to avoid overlap
- Render measurement point labels when Excel data exists
- Toggle contour grid display (hidden by default, light gray when shown)
- Optional info panel on the right side of wafer chart
- Info panel includes `total frames` (count of complete frames)
- Info panel includes `total dies` (count of complete dies)
- Info panel includes `edge exclude`, `top`, `bottom`, and `frame bottom gap` (mm)
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
| `array X` | Number of dies per frame in X direction | count |
| `array Y` | Number of dies per frame in Y direction | count |
| `top` | Start frame placement from wafer top minus this value | mm |
| `bottom` | Minimum allowed frame-bottom gap from wafer bottom (default `3.0`) | mm |
| `frame offset X` | Frame grid X offset | um |
| `frame offset Y` | Frame grid Y offset | um |
| `offsetX` | Site offset X from frame lower-left origin | um |
| `offsetY` | Site offset Y from frame lower-left origin | um |
| `wafer diameter` | Wafer diameter | mm |
| `flat` | Wafer edge type: `47.5 mm`, `57.5 mm`, `notch-180`, `notch-135` (default `57.5 mm`) | mm / type |
| `edge exclude` | Inward shrink distance from original wafer edge (default `2.5`) | mm |
| `show contour` | Show/hide contour (only effective when Excel is uploaded) | bool |
| `show contour grid` | Show/hide contour grid (default hidden) | bool |
| `show info panel` | Show/hide parameter summary text at chart right side | bool |
| `enable lasermark frame` | Show/hide laser mark rectangle | bool |
| `edge-to-mark_top` | Distance from wafer edge to the outer/top side of the laser mark | mm |
| `char-height` | Laser mark rectangle height | mm |
| `marker length` | Laser mark rectangle width/length | mm |
| `position` | Clockwise angle from wafer top; rectangle rotates with this angle | deg |
| `title` | Custom chart title (overridden by Excel filename when Excel is uploaded) | text |

Rules:

- `offsetX < stepX`
- `offsetY < stepY`
- default wafer diameter is `150 mm`
- default `top` is `10 mm`
- default `bottom` is `3 mm`
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
- `array X` and `array Y` are unitless die counts per frame
- `wafer diameter`, `top`, `edge exclude`, and flat size use unit `mm`
- `notch-180` is drawn as an approximate V-notch at 180 degrees
- `notch-135` is drawn as an approximate V-notch rotated to 135 degrees
- laser mark frame uses the real wafer edge along the selected angle, so flat and notch edge types affect its placement
- frame lines are light red dashed lines
- die grid lines are lighter gray lines
- die size is derived by `dieW = stepX / arrayX`, `dieH = stepY / arrayY`
- complete dies can be drawn outside frame area if they still fully fit inside effective wafer boundary
- only fully complete rectangular frames are drawn
- `total frames` in info panel counts only complete rectangular frames
- `total dies` in info panel counts only complete die rectangles
- frame vertical placement starts from top and goes downward
- `frame bottom gap` in info panel is the distance from arranged frame bottom edge to wafer bottom edge, and it will not be smaller than `bottom`
- contour grid is optional and shown in light gray when enabled
