# waferMap

A Streamlit app for plotting wafer thickness contour maps from Excel measurement data.

by cnwang, 2026/03


## Features

- Upload an Excel file with `siteX`, `siteY`, and `thickness`
- Input wafer map parameters: `stepX`, `stepY`, `offsetX`, `offsetY`, `wafer diameter`, `flat`
- Convert site coordinates into absolute wafer coordinates
- Draw wafer outline with `47.5 mm`, `57.5 mm`, or `notch`
- Render contour map and measurement point labels
- Export the chart as a `.jpg` using the same base filename as the Excel file

## Input Data

The Excel file must contain these columns:

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
| `wafer diameter` | Wafer diameter | mm |
| `flat` | Wafer edge type: `47.5 mm`, `57.5 mm`, `notch` | mm / type |

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

- Interactive Streamlit view of the wafer contour
- Thickness labels displayed at each measurement point
- A `.jpg` file saved in the working directory using the uploaded Excel filename
- A download button in the Streamlit UI for the generated image

## Files

- `app.py`: Streamlit UI
- `wafermap_core.py`: calculation and plotting logic
- `requirements.txt`: Python dependencies

## Notes

- `thickness` uses unit `A`
- `stepX`, `stepY`, `offsetX`, `offsetY` use unit `um`
- `wafer diameter` and flat size use unit `mm`
- `notch` is currently drawn as an approximate V-notch
