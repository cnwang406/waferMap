# Wafer Data Viewer

A comprehensive Streamlit application for wafer data visualization, contour mapping, and KGDmap analysis.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.55-FF4B4B.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/plotly-5.18-2D3E50.svg)](https://plotly.com/)
[![Pandas](https://img.shields.io/badge/pandas-2.3-150458.svg)](https://pandas.pydata.org/)
[![Matplotlib](https://img.shields.io/badge/matplotlib-3.10-11557c.svg)](https://matplotlib.org/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**Version 2.0** | by cnwang, 2026/04

## Features

### Core Functionality
- **Excel/CSV Upload Support**: Optional data input with automatic format detection
- **KGDmap Integration**: Support for KGDmap CSV format with Lot/Wafer headers
- **Tabbed Interface**: Three main views - Wafer Map, CP View, and Wafer+CP Overlay
- **Config Management**: Save/load configurations with customizable filenames
- **About Dialog**: Comprehensive application information popup

### Visualization Modes

#### Wafer Map Tab
- Standard wafer contour visualization with measurement data
- Frame-only preview when no data is uploaded
- Interactive contour plots with customizable styling
- Optional die labels and grid overlays
- Laser mark rectangle overlay with adjustable parameters

#### CP View Tab (KGDmap Special View)
- Interactive charts for KGDmap data analysis
- Die-based visualization with proper aspect ratios
- Multiple item selection and plotting
- Plotly-powered interactive visualizations

#### Wafer+CP Overlay Tab
- Combined wafer map with KGDmap data overlay
- Color-coded die values with borders
- Mismatch detection between wafer layout and KGDmap data
- Export combined visualizations as JPG

### Parameters & Configuration
- **Wafer Geometry**: Diameter, flat type (47.5mm, 57.5mm, notch-180, notch-135)
- **Frame Layout**: Step sizes, array configuration, offsets
- **Site Positioning**: Coordinate transformations and offsets
- **Edge Processing**: Edge exclusion and effective boundary calculation
- **Laser Marking**: Position, size, and orientation controls
- **Color Customization**: Frame lines, die lines, wafer edges, contour colors
- **Display Options**: Contour style, grid visibility, info panels

### Input Data Formats

#### Standard Excel/CSV Format
| Column | Description | Unit |
| --- | --- | --- |
| `siteX` | Site X index | count |
| `siteY` | Site Y index | count |
| `thickness` | Measured thickness | Å |

#### KGDmap CSV Format
- Header rows (1-10): Lot, Wafer, Product, Date, Time, Tester info
- Data rows (11+): chip_row, chip_column, and measurement columns
- Automatic die coordinate conversion (dieR, dieC)

### Output Features
- Interactive Streamlit web interface
- High-resolution JPG exports
- Automatic filename generation
- Download buttons for all generated images
- Configurable parameter templates for Excel files

## Input Data (Optional)

### Standard Format (Excel/CSV)
Required columns for measurement data:

| Column | Description | Unit |
| --- | --- | --- |
| `siteX` | Site X index | count |
| `siteY` | Site Y index | count |
| `thickness` | Measured thickness | Å |

### KGDmap Format (CSV)
- **Header Section** (rows 1-10): Metadata including Lot, Wafer, Product, Date, Time, Tester information
- **Data Section** (rows 11+): chip_row, chip_column, and measurement columns
- **Automatic Processing**: Converts chip coordinates to dieR/dieC format
- **Multi-file Support**: Can upload multiple KGDmap files for batch processing

## Parameters

### Core Parameters
| Parameter | Description | Unit | Default |
| --- | --- | --- | --- |
| `stepX` | Frame width | µm | 10000 |
| `stepY` | Frame height | µm | 10000 |
| `array X` | Dies per frame in X direction | count | 1 |
| `array Y` | Dies per frame in Y direction | count | 1 |
| `frame offset X` | Frame grid X offset | µm | 0 |
| `frame offset Y` | Frame grid Y offset | µm | 0 |

### Positioning Parameters
| Parameter | Description | Unit | Default |
| --- | --- | --- | --- |
| `offsetX` | Site offset X from frame origin | µm | 0 |
| `offsetY` | Site offset Y from frame origin | µm | 0 |
| `top` | Frame placement from wafer top | mm | 10.0 |
| `bottom` | Minimum frame-bottom gap | mm | 3.0 |

### Wafer Geometry
| Parameter | Description | Unit | Default |
| --- | --- | --- | --- |
| `wafer diameter` | Wafer diameter | mm | 150.0 |
| `flat` | Edge type: `47.5 mm`, `57.5 mm`, `notch-180`, `notch-135` | - | `57.5 mm` |
| `edge exclude` | Inward shrink from wafer edge | mm | 2.5 |

### Laser Mark Parameters
| Parameter | Description | Unit | Default |
| --- | --- | --- | --- |
| `enable lasermark frame` | Show/hide laser mark | - | false |
| `edge-to-mark_top` | Distance from edge to mark | mm | 3.0 |
| `char-height` | Mark rectangle height | mm | 1.3 |
| `marker length` | Mark rectangle width | mm | 11.0 |
| `position` | Clockwise angle from top | deg | 0 |

### Display Parameters
| Parameter | Description | Default |
| --- | --- | --- |
| `show contour` | Enable contour visualization | true |
| `contour style` | filled / lines / filled+lines / heatmap | filled |
| `show contour grid` | Display contour grid lines | false |
| `show die labels` | Show die coordinate labels | false |
| `show info panel` | Display parameter summary | false |
| `title` | Custom chart title | wafer_frame_preview |

### Color Customization
| Parameter | Description | Default |
| --- | --- | --- |
| `frame line color` | Frame boundary lines | #f4a3a3 |
| `die line color` | Die grid lines | #ececec |
| `effective edge color` | Inner boundary | #f4a3a3 |
| `wafer edge color` | Outer boundary | #000000 |
| `contour grid color` | Contour grid | #d9d9d9 |

## Coordinate System

### Position Calculation
```python
# Convert site indices to absolute coordinates
posX_mm = (siteX * stepX_um + offsetX_um) / 1000.0
posY_mm = (siteY * stepY_um + offsetY_um) / 1000.0
```

### Die Size Calculation
```python
dieWidth_um = stepX_um / arrayX
dieHeight_um = stepY_um / arrayY
```

### KGDmap Coordinate Mapping
- `chip_row` → `dieR` (1-based indexing)
- `chip_column` → `dieC` (1-based indexing)
- Automatic offset calculation from minimum values

## Installation

```bash
# Clone or download the repository
cd wafermap

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Running the Application
```bash
streamlit run app.py
```

### Basic Workflow
1. **Configure Parameters**: Set wafer geometry, frame layout, and display options in the sidebar
2. **Upload Data**: 
   - Excel/CSV with siteX, siteY, thickness columns for standard visualization
   - KGDmap CSV files for advanced analysis
3. **Select View**: Choose between Wafer Map, CP View, or Combined Overlay tabs
4. **Customize**: Adjust colors, labels, and display options
5. **Export**: Download generated visualizations as JPG files
6. **Save Config**: Export parameter settings for reuse

### Configuration Management
- **Save Config**: Export current settings to JSON with custom filename
- **Load Config**: Import previously saved configurations
- **Parameter Templates**: Auto-generate Excel templates with current parameters

## Output

### Visualization Types
- **Wafer Map**: Standard contour plots with frame and die overlays
- **CP View**: Interactive KGDmap analysis with Plotly charts
- **Combined View**: Overlay of KGDmap data on wafer geometry

### Export Formats
- High-resolution JPG images
- Automatic filename generation based on input data
- Download buttons for all generated visualizations
- Config JSON files for parameter persistence

### Info Panel Features
- Total frame and die counts
- Edge exclusion and boundary measurements
- Coordinate system information
- Parameter summary with units

## Project Structure

```
wafermap/
├── app.py                 # Main Streamlit application
├── wafermap_core.py       # Core calculation and plotting logic
├── kgdmapviewer.py        # KGDmap visualization and processing
├── requirements.txt       # Python dependencies
├── README.md             # This documentation
├── LICENSE               # MIT License
└── test.txt              # Test data file
```

### Key Modules

#### app.py
- Streamlit web interface
- Parameter management and validation
- File upload and format detection
- Tabbed visualization interface
- Config save/load functionality

#### wafermap_core.py
- Wafer geometry calculations
- Frame and die layout algorithms
- Contour interpolation
- Coordinate transformations

#### kgdmapviewer.py
- KGDmap data processing
- Interactive chart generation
- Die-based visualization
- Overlay rendering logic

## Technical Notes

### Units and Conventions
- **Thickness**: Å (Angstroms)
- **Dimensions**: µm for precision, mm for display
- **Coordinates**: Origin at wafer center (0,0)
- **Angles**: Clockwise from top (0° = 12 o'clock position)

### Wafer Edge Types
- `47.5 mm` / `57.5 mm`: Standard flat edge wafers
- `notch-180`: V-notch at bottom (180°)
- `notch-135`: V-notch at 135° position

### Rendering Optimizations
- Contour interpolation without SciPy dependency
- Automatic layout adjustment for colorbars and info panels
- Efficient die and frame boundary calculations
- Memory-optimized image generation

### Compatibility
- **Python**: 3.8+ (tested with 3.13)
- **Streamlit**: 1.28+ (tested with 1.55)
- **Plotly**: 5.18+ for interactive charts
- **Matplotlib**: 3.10+ for static plots

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see [LICENSE](./LICENSE) for details.

---

**Author**: cnwang  
**Version**: 2.0  
**Last Updated**: 2026/04
- frame vertical placement starts from top and goes downward
- `frame bottom gap` in info panel is the distance from arranged frame bottom edge to wafer bottom edge, and it will not be smaller than `bottom`
- contour grid is optional and shown in light gray when enabled
