from __future__ import annotations

import sys
import json
from pathlib import Path

# ensure project root is on sys.path so `src` imports work when run directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dash
from dash import html, dcc
import plotly.express as px
import pandas as pd
import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash.dependencies import Input, Output, State, ALL

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
# overlay metadata is written to app/assets/overlays/munich_overlays.json
OVERLAY_META = PROJECT_ROOT / "app" / "assets" / "overlays" / "munich_overlays.json"

city = get_city_config("munich")


app = dash.Dash(__name__, external_stylesheets=["https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css"])
server = app.server

# build base map with Esri World Imagery
esri_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
base_layer = dl.TileLayer(url=esri_url, attribution="Esri World Imagery")

# load overlays metadata
if OVERLAY_META.exists():
    with open(OVERLAY_META, "r", encoding="utf-8") as fh:
        overlays = json.load(fh)
else:
    overlays = {}

# human-friendly mapping for layer names
HUMAN_NAMES = {
    'munich_ndvi_2024.png': 'NDVI (Vegetation)',
    'munich_lst_mean_2023_2024.png': 'Land Surface Temp (mean)',
}
for k in list(overlays.keys()):
    if k not in HUMAN_NAMES:
        # friendly label from filename
        label = k.replace('munich_', '').replace('.png', '').replace('_', ' ').title()
        HUMAN_NAMES[k] = label

# prepare per-layer controls (pattern-matching ids)
layer_controls = []
for name in overlays.keys():
    chk_id = {'type': 'layer-checkbox', 'index': name}
    sld_id = {'type': 'layer-slider', 'index': name}
    # minimalist slider + checkbox
    layer_controls.append(html.Div([
        dcc.Checklist(id=chk_id, options=[{'label': HUMAN_NAMES[name], 'value': name}], value=[name], persistence=True, inputStyle={'marginRight':'8px'}),
        dcc.Slider(id=sld_id, min=0.0, max=1.0, step=0.01, value=0.8, tooltip={'placement':'bottom'}, updatemode='drag', marks=None)
    ], style={'marginBottom': '10px', 'fontSize': '13px'}))

# time series data (demo summary)
summary_csv = PROJECT_ROOT / 'data' / 'processed' / 'summary' / 'munich_era5_daily_summary.csv'
ts_df = None
if summary_csv.exists():
    try:
        ts_df = pd.read_csv(summary_csv, parse_dates=['date'])
    except Exception:
        ts_df = None

# header
header = html.Div([
    html.Div('Urban Climate Adaptation Tool', style={'fontSize': '20px', 'fontWeight': '600'}),
    html.Div('Munich — Interactive layers, opacity, and time series', style={'fontSize': '12px', 'color': '#666'})
], style={'display': 'flex', 'flexDirection': 'column', 'padding': '12px 18px', 'background': '#FFFFFF', 'borderBottom': '1px solid #eee'})

# controls panel (left)
master_toggle = dcc.Checklist(id='master-toggle', options=[{'label':'Map overlays','value':'map'},{'label':'Plots','value':'plots'}], value=['map','plots'], labelStyle={'display':'inline-block','marginRight':'12px'})

legend_toggle = dcc.Checklist(id='legend-toggle', options=[{'label':'Show legend','value':'legend'}], value=[], labelStyle={'display':'inline-block'})

controls = html.Div([
    html.H3('Layers', style={'marginTop': '0'}),
    html.Div(master_toggle, style={'marginBottom':'8px'}),
    html.Div(layer_controls, id='layer-controls-container'),
    html.Div(legend_toggle, style={'marginTop':'8px'}),
    html.Div(id='legend-container', style={'marginTop':'8px'}),
    html.Hr(),
    html.H3('Time Series', style={'marginTop': '8px'}),
    dcc.Checklist(id='ts-checklist', options=[{'label': 'Air temp (2m)', 'value': 'temp_2m_c'}, {'label': 'Precipitation (mm)', 'value': 'total_precip_mm'}, {'label': 'ERA5 LST (c)', 'value': 'lst_c'}], value=['lst_c']),
    dcc.Graph(id='ts-graph', style={'height': '220px'})
], style={'width': '320px', 'padding': '16px', 'background': 'rgba(255,255,255,0.95)', 'position': 'absolute', 'right': '10px', 'top': '112px', 'zIndex': '999', 'borderRadius': '8px', 'boxShadow': '0 6px 18px rgba(0,0,0,0.08)'} )

# popup area above map on the left for selected plots
plot_popup = html.Div(id='plot-popup', style={'position':'fixed','left':'20px','top':'84px','zIndex': '2100','background':'rgba(255,255,255,0.98)','padding':'10px','borderRadius':'6px','boxShadow':'0 10px 30px rgba(0,0,0,0.16)','display':'none','maxWidth':'520px','pointerEvents':'auto'})

map_component = dl.MapContainer(center=(city.center_lat, city.center_lon), zoom=11, children=[
    dl.TileLayer(url=esri_url, attribution='Esri World Imagery'),
    dl.LayerGroup(id='overlay-group'),
], style={'width': '100%', 'height': 'calc(100vh - 64px)', 'margin': '0px'}, id='map')

bbox = city.bbox  # (minx, miny, maxx, maxy)

# map component with investigation bbox rectangle
map_component = dl.MapContainer(center=(city.center_lat, city.center_lon), zoom=11, children=[
    dl.TileLayer(url=esri_url, attribution='Esri World Imagery'),
    dl.LayerGroup(id='overlay-group'),
    dl.Rectangle(bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]], color='#ff7800', weight=2, fill=False)
], style={'width': '100%', 'height': 'calc(100vh - 64px)', 'margin': '0px'}, id='map')

# right-side collapsible details (native HTML <details>)
details = html.Details([
    html.Summary('Layers & Time Series', style={'cursor': 'pointer', 'padding': '8px 10px', 'background': '#fff', 'border': '1px solid #eee', 'borderRadius': '6px', 'boxShadow': '0 4px 12px rgba(0,0,0,0.06)', 'fontSize': '13px'}),
    controls,
], style={'position':'absolute','right':'10px','top':'72px','zIndex':'1000','width':'360px'})

app.layout = html.Div([header, html.Div([map_component, details, plot_popup])])


@app.callback(
    Output('overlay-group', 'children'),
    [Input({'type': 'layer-checkbox', 'index': ALL}, 'value'), Input({'type': 'layer-slider', 'index': ALL}, 'value'), Input('master-toggle', 'value')]
)
def render_overlays(checkbox_values, slider_values, master_values):
    # checkbox_values: list of lists (selected values per checkbox control)
    # slider_values: list of opacity floats in the same order
    items = []
    # if master toggle doesn't include 'map', return empty
    if not master_values or 'map' not in master_values:
        return items
    # Build overlays in the same order as controls
    for idx, chk in enumerate(checkbox_values):
        if not chk:
            continue
        name = chk[0]
        info = overlays.get(name)
        if not info:
            continue
        opacity = 0.8
        try:
            opacity = float(slider_values[idx])
        except Exception:
            opacity = 0.8
        png_url = '/' + info['png']
        bounds = info['bounds']
        img = dl.ImageOverlay(url=png_url, bounds=bounds, opacity=opacity, id={'type': 'overlay-image', 'index': name})
        items.append(img)
    return items


@app.callback(
    [Output('ts-graph', 'figure'), Output('plot-popup', 'children'), Output('plot-popup', 'style')],
    [Input('ts-checklist', 'value'), Input('master-toggle', 'value')]
)
def update_timeseries(selected, master_values):
    # build figure
    if ts_df is None or not selected:
        fig = px.line()
    else:
        df = ts_df.copy()
        fig = px.line()
        for col in selected:
            if col in df:
                fig.add_scatter(x=df['date'], y=df[col], mode='lines', name=col)
        fig.update_layout(margin=dict(l=20, r=10, t=20, b=20), template='simple_white')

    # show popup only if master toggle includes 'plots'
    if master_values and 'plots' in master_values and selected:
        popup_children = html.Div([
            html.Div('Time Series', style={'fontWeight':'600','marginBottom':'6px'}),
            dcc.Graph(figure=fig, style={'height':'240px','width':'440px'}),
            html.Button('Close', id='close-popup', n_clicks=0, style={'marginTop':'6px'})
        ])
        style = {'display':'block'}
    else:
        popup_children = []
        style = {'display':'none'}

    return fig, popup_children, style


@app.callback(Output('plot-popup', 'style'), Input('close-popup', 'n_clicks'), State('plot-popup', 'style'))
def close_popup(n, style):
    if not style:
        style = {'display':'none'}
    if n and n > 0:
        style['display'] = 'none'
    return style


@app.callback(Output('controls-collapse', 'is_open'), Input('controls-toggle', 'n_clicks'), State('controls-collapse', 'is_open'))
def toggle_controls(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(Output('legend-container', 'children'), [Input({'type': 'layer-checkbox', 'index': ALL}, 'value'), Input('legend-toggle', 'value')])
def update_legend(check_values, legend_values):
    # if legend not requested, return empty
    if not legend_values or 'legend' not in legend_values:
        return []
    items = []
    for chk in check_values:
        if not chk:
            continue
        name = chk[0]
        label = HUMAN_NAMES.get(name, name)
        # create a simple legend swatch depending on name
        if 'ndvi' in name:
            grad = 'linear-gradient(90deg,#e6f4ea,#1b7837)'
        elif 'lst' in name:
            grad = 'linear-gradient(90deg,#000004,#7b2c6f,#f1603a,#fdb863)'
        elif 'water' in name:
            grad = 'linear-gradient(90deg,#dbefff,#2b8cbe)'
        else:
            grad = 'linear-gradient(90deg,#ddd,#666)'
        swatch = html.Div([
            html.Div(style={'width':'120px','height':'14px','background':grad,'borderRadius':'3px','display':'inline-block','marginRight':'8px'}),
            html.Span(label, style={'verticalAlign':'middle','fontSize':'13px'})
        ], style={'marginBottom':'6px'})
        items.append(swatch)
    return items


if __name__ == "__main__":
    # Run without debug/hot-reload for stability when developing locally
    app.run(debug=False, port=8050)
