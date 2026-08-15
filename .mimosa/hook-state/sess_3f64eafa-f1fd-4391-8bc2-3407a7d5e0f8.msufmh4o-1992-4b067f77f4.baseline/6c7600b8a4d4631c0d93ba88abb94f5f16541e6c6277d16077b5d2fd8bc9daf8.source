# Flint Chart — Agent Skill

## When to use this skill

Use Flint Chart when the user requests any of the following:
- A chart or visualization ("make a chart", "visualize this", "plot the data")
- A graph, diagram, or data graphic
- A report that includes charts
- PNG or SVG export of a visualization
- A static chart for embedding in a document, email, or dashboard tile

Do NOT use Flint Chart for interactive dashboard widgets where hover/zoom/brush is needed — those use the GPT-Vis protocol with AntV G2.

## Flint ChartAssemblyInput Schema

Flint uses a single unified schema for approximately 40 chart types across three backends (Vega-Lite, ECharts, Chart.js).

### Required fields

```json
{
  "chartType": "Bar Chart",
  "data": {
    "values": [
      {"x_field": "value", "y_field": 123}
    ]
  }
}
```

### Full schema

```json
{
  "chartType": "Bar Chart",
  "encodings": {
    "x": {"field": "column_name"},
    "y": {"field": "column_name"},
    "color": {"field": "column_name"},
    "size": {"field": "column_name"}
  },
  "baseSize": {"width": 600, "height": 400},
  "semantic_types": {
    "column_name": "Category",
    "other_column": "Quantity",
    "date_column": "Temporal"
  },
  "data": {
    "values": [...]
  }
}
```

### Supported Chart Types

**Categorical**: Bar Chart, Stacked Bar Chart, Grouped Bar Chart, Pie Chart, Donut Chart
**Trend/Temporal**: Line Chart, Multi-series Line Chart, Area Chart, Stacked Area Chart
**Distribution**: Histogram, Box Plot, Scatter Chart
**Relational**: Heatmap, Bubble Chart

### Semantic Types

- `Category` — discrete labels (names, regions, IDs)
- `Quantity` — continuous numeric values (revenue, counts, percentages)
- `Temporal` — dates, timestamps, years

### Backend Selection

- **Vega-Lite** (recommended): Best for SVG output, typography, and complex statistical charts
- **ECharts**: More chart types (Sankey, radar, treemap), better for Asian character rendering
- **Chart.js**: Fastest rendering, PNG only, good for simple dashboards

### Data Format

Prefer `data.values` for small datasets (< 100 rows). For larger datasets, write to a temp file in `FLINT_MCP_DATA_ROOTS` and reference via `data.url`.

## Integration with GenBI Pipeline

1. The NL2SQL agent generates a SQL query from the user's natural language
2. The SQL is executed against the data source, producing a result set
3. The ChartGenAgent analyzes the result set, infers semantic types, and selects a chart type
4. The ChartGenAgent produces a `ChartAssemblyInput` spec
5. The FlintChartBridge renders the spec via Flint MCP
6. The result (PNG/SVG) is embedded in the chat response
