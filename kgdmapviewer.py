"""
KGDmap Viewer - Visualization for KGD (Known Good Die) test data in KGDmap format
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import streamlit as st


def parse_kgdmap_data(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """
    Parse KGDmap CSV data.
    When read with skiprows=11 and header=0:
    - df already has proper column names
    - All rows are data (header extracted separately by app)
    
    Returns: (empty_dict_for_compat, data_dataframe)
    """
    # Since header is extracted separately in app.py, just return empty dict and data
    return {}, df


def get_kgdmap_items(data_df: pd.DataFrame) -> list[str]:
    """
    Get list of available items (columns) excluding chip_row and chip_column.
    Prepend "(r,c)" for debug purposes.
    """
    if data_df.empty:
        return []
    
    items = ["(r,c)"]  # Debug option to show coordinates
    exclude_cols = {"chip_row", "chip_column"}
    
    for col in data_df.columns:
        col_str = str(col).strip().lower()
        if col_str not in exclude_cols:
            items.append(str(col).strip())
    
    return items


def prepare_kgdmap_grid(data_df: pd.DataFrame, item_name: str) -> tuple[np.ndarray, int, int]:
    """
    Prepare grid data for visualization.
    Coordinates: chip_row, chip_column (1-indexed, top-left = 1,1)
    
    Returns: (grid_array, max_row, max_col)
    """
    if data_df.empty:
        return np.array([]), 0, 0
    
    # Convert chip_row and chip_column to numeric
    data_df = data_df.copy()
    data_df['chip_row'] = pd.to_numeric(data_df['chip_row'], errors='coerce')
    data_df['chip_column'] = pd.to_numeric(data_df['chip_column'], errors='coerce')
    
    # Find grid dimensions
    max_row = int(data_df['chip_row'].max())
    max_col = int(data_df['chip_column'].max())
    
    # Create grid initialized with NaN
    grid = np.full((max_row, max_col), np.nan)
    
    # Fill grid with values
    if item_name == "(r,c)":
        # Special case: show row value (can use row or encode as r*100+c)
        for idx, row in data_df.iterrows():
            r = int(row['chip_row']) - 1  # Convert to 0-indexed
            c = int(row['chip_column']) - 1
            if 0 <= r < max_row and 0 <= c < max_col:
                # Store as row index (visible in colormap)
                grid[r, c] = r + 1  # Use 1-indexed row value
    else:
        # Get values from the selected item column
        if item_name in data_df.columns:
            values = pd.to_numeric(data_df[item_name], errors='coerce')
            for idx, row in data_df.iterrows():
                r = int(row['chip_row']) - 1
                c = int(row['chip_column']) - 1
                if 0 <= r < max_row and 0 <= c < max_col:
                    grid[r, c] = values.iloc[idx]
    
    return grid, max_row, max_col


def create_kgdmap_figure(
    grid: np.ndarray,
    max_row: int,
    max_col: int,
    item_name: str,
    header_info: dict | None = None,
) -> plt.Figure:
    """
    Create matplotlib figure for KGDmap visualization.
    """
    if header_info is None:
        header_info = {}
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create heatmap
    im = ax.imshow(grid, cmap='RdYlGn_r', aspect='auto', origin='upper')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label=item_name if item_name != "(r,c)" else "Chip Row")
    
    # Set ticks
    ax.set_xticks(np.arange(0, max_col, max(1, max_col // 10)))
    ax.set_yticks(np.arange(0, max_row, max(1, max_row // 10)))
    
    # Labels
    ax.set_xlabel("Chip Column (1-indexed)")
    ax.set_ylabel("Chip Row (1-indexed)")
    ax.set_title(f"KGDmap: {item_name}")
    
    # Add grid lines
    ax.set_xticks(np.arange(-0.5, max_col, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, max_row, 1), minor=True)
    ax.grid(which='minor', color='gray', linestyle='-', linewidth=0.5, alpha=0.3)
    
    # Add text annotations for values (if grid is not too large)
    if max_row <= 20 and max_col <= 20:
        for i in range(max_row):
            for j in range(max_col):
                if not np.isnan(grid[i, j]):
                    text = ax.text(j, i, f'{grid[i, j]:.1f}',
                                 ha="center", va="center", color="black", fontsize=8)
    
    # Add header info to figure
    if header_info:
        header_text = "\n".join([f"{k}: {v}" for k, v in list(header_info.items())[:5]])
        fig.text(0.02, 0.98, header_text, transform=fig.transFigure,
                 fontsize=9, verticalalignment='top', family='monospace',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def render_kgdmap_viewer(kgdmap_df: pd.DataFrame):
    """
    Main function to render KGDmap viewer in Streamlit.
    Retrieves header info from session_state if available.
    """
    if kgdmap_df is None or kgdmap_df.empty:
        st.warning("KGDmap 數據為空")
        return
    
    # Parse data
    _, data_df = parse_kgdmap_data(kgdmap_df)
    
    # Get header info from session_state (extracted in app.py)
    header_info = st.session_state.get("kgdmapHeader", {})
    
    if data_df.empty:
        st.error("無法解析 KGDmap 數據")
        return
    
    # Display header info
    st.subheader("KGDmap 基本資訊")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Lot", header_info.get("Lot", "N/A"))
    with col2:
        st.metric("Wafer", header_info.get("Wafer", "N/A"))
    with col3:
        st.metric("Product", header_info.get("Product", "N/A"))
    
    col4, col5 = st.columns(2)
    with col4:
        st.metric("Date", header_info.get("Date", "N/A"))
    with col5:
        st.metric("Total Chips", len(data_df))
    
    # Item selector
    st.subheader("數據可視化")
    available_items = get_kgdmap_items(data_df)
    
    if not available_items:
        st.error("未找到可用的 item 列")
        return
    
    selected_item = st.selectbox(
        "選擇要顯示的 Item",
        available_items,
        help="(r,c) 用於顯示 chip 座標位置，數值為 chip_row (1-indexed)"
    )
    
    # Prepare and display grid
    grid, max_row, max_col = prepare_kgdmap_grid(data_df, selected_item)
    
    if grid.size == 0:
        st.error("無法生成網格數據")
        return
    
    # Create figure
    fig = create_kgdmap_figure(grid, max_row, max_col, selected_item, header_info)
    
    # Display figure
    st.pyplot(fig, use_container_width=True)
    
    # Display data table
    with st.expander("詳細數據表", expanded=False):
        display_df = data_df[['chip_row', 'chip_column', selected_item]].copy()
        display_df['chip_row'] = pd.to_numeric(display_df['chip_row'], errors='coerce')
        display_df['chip_column'] = pd.to_numeric(display_df['chip_column'], errors='coerce')
        display_df[selected_item] = pd.to_numeric(display_df[selected_item], errors='coerce')
        st.dataframe(display_df.sort_values(['chip_row', 'chip_column']), use_container_width=True)
    
    # Display statistics
    with st.expander("統計資訊", expanded=False):
        numeric_cols = ['chip_row', 'chip_column']
        if selected_item != "(r,c)":
            numeric_cols.append(selected_item)
        
        for col in numeric_cols:
            if col in data_df.columns:
                values = pd.to_numeric(data_df[col], errors='coerce')
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(f"{col} Min", f"{values.min():.2f}")
                with col2:
                    st.metric(f"{col} Max", f"{values.max():.2f}")
                with col3:
                    st.metric(f"{col} Mean", f"{values.mean():.2f}")
                with col4:
                    st.metric(f"{col} Std", f"{values.std():.2f}")
    
    plt.close(fig)
