# Wireframes

## User Interface Overview

### Main Dashboard

- **Sidebar:** Upload, parameter selection, session management
- **Chart Area:** Interactive Plotly chart (choose any parameter on X/Y)
- **Time Interval:** Slider and start/end input
- **Data Table:** Synced with chart selection
- **Export & Session:** Save/load session, export data/chart
- **Assistant:** (Future) Chat with LLM agent for analysis help
- **Map View:** (Future) Export or view flight path in Google Earth

_See `/docs/wireframes/` for detailed diagrams._

## Main Dashboard Layout

```less
+-----------------------------------------------------------------------------------+
| FTIAS: Flight Test Interactive Analysis Suite                                     |
|-----------------------------------------------------------------------------------|
| [Sidebar: Parameter Browser]      |    [Main Chart Area]                          |
|-----------------------------------|-----------------------------------------------|
| - Upload Data                     |    +-------------------------------+         |
| - File List / Session List        |    |                               |         |
| - Search Parameter                |    |         [Plotly Chart]         |         |
| - Parameter Tree/List             |    |    (Time vs Altitude, etc.)    |         |
|   - [ ] Time                      |    |    [Zoom][Pan][Select][Export] |         |
|   - [ ] Velocity                  |    +-------------------------------+         |
|   - [ ] Altitude                  |               [Data Table]                   |
|   - ...                           |   +-------------------------------+         |
|                                   |   |      Data Preview Table         |         |
|                                   |   +-------------------------------+         |
|-----------------------------------|-----------------------------------------------|
| [User Menu]   [Settings]   [Help] | [LLM Agent Chat]   [Export]   [Save Session] |
+-----------------------------------------------------------------------------------+
```

### Chart Builder Panel

Parameter Selection (X, Y, [Z/Color])
    Dropdown menus:
        X Axis: [Time ▼]
        Y Axis: [Altitude ▼]
        (Optional) Color/Z: [Velocity ▼]
Chart Type Selector
    [ Line ] [ Scatter ] [ Histogram ] [ 2Y-Axis ]
Time Interval Selector
    Slider: [=====|====|====|====]
    Input: Start [] End []
    Button: [Apply Filter]
Chart Interactions
    [ Zoom ] [ Pan ] [ Reset ] [ Export ▼ ]
        PNG
        HTML
        CSV Data
Annotation/Notes
    [Add Note] button, pin notes on chart

### Data Table / Preview

Synchronized with selected time interval and parameters
Paginated and filterable
Columns: Time | Parameter 1 | Parameter 2 | ...

### LLM Assistant Panel (Future/Expandable)

```lua
+-----------------------------------+
|  🤖 Ask FTIAS Assistant:          |
|  [Type your question here...]     |
|                                   |
|  Examples:                        |
|  - "Summarize this test"          |
|  - "Plot airspeed vs altitude"    |
|  - "Highlight anomalies"          |
|                                   |
|  [Send]                           |
|-----------------------------------|
|  [Assistant Response Here]        |
+-----------------------------------+
```

### Flight Path / Map View (Future Phase)

Button: [Plot Trajectory in Google Earth]
Triggers export of KML/KMZ for direct download
(Optional In-App Map)
Tab: [Map View]
Embedded CesiumJS/Kepler.gl map with:
Colored flight path (by speed, altitude, etc.)
Timeline animation bar
Sync with chart selection

### Remarks

Visual References
(Use these terms for quick Figma/Balsamiq prototyping)
    Sidebar: Collapsible; displays parameters and session controls
    Top Bar: Project name, user profile, settings, and help
    Main Panel: Plotly chart area, chart controls above or below
    Bottom Pane: Data table, export options
    Floating Chat Widget: Expandable for LLM assistant
