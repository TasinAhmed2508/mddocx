# Phase 8 — Native Editable Charts and Structured Data

Version 0.9.0 adds structured data as a first-class compiler input while preserving the project rule that logically editable Word content should remain editable.

## Chart syntax

````markdown
```chart {#fig-performance caption="Quarterly performance"}
type: column
title: Revenue and profit
source: data/quarterly.csv
category: Quarter
series_fields: [Revenue, Profit]
```
````

Supported chart types: `column`, `bar`, `line`, `pie`, `scatter`.

Charts are stored as native Office ChartML and each chart has a deterministic embedded Excel workbook under `word/embeddings/`. Word users can edit the chart and its data instead of editing a raster screenshot.

## Inline data

````markdown
```chart
type: pie
title: Share
categories: [A, B, C]
series:
  - name: Value
    values: [20, 30, 50]
```
````

## Imported tables

````markdown
```data-table {#tbl-benchmark caption="Benchmark data"}
source: data/results.json
columns: [Model, Accuracy, Latency]
```
````

The output is a native Word table and uses the same table width/pagination/caption/reference engine as ordinary Markdown tables.

## Data formats

- CSV: first row is the header.
- JSON: array of objects, or an object whose `rows` member is an array of objects.
- UTF-8/UTF-8 BOM are supported.

## Security

Structured data is never executed. Local data paths are resolved beneath the document/project base directory, traversal is rejected, and project mode records chart/table data files as build dependencies. Row, column, chart-series, and chart-point limits are configurable.

## Project mode

Chapter-relative chart/data paths are rebased to the project root during AST assembly. Editing a CSV or JSON dependency changes the project fingerprint and triggers an incremental rebuild.

## Inspection

`mddocx inspect output.docx --strict` reports native chart and embedded workbook counts and validates all internal chart/workbook relationships.

`mddocx data inspect data/results.csv --json` validates input shape before rendering.
