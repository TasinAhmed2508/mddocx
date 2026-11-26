# Native Office charts

Chart fences generate editable ChartML backed by an embedded deterministic XLSX workbook.

Category labels and series share a range long enough to include every supplied value.
Missing labels remain blank. Missing values, including explicit YAML `null` entries,
remain blank workbook cells and chart gaps. When categories are omitted entirely,
the compiler generates sequential category values. Scatter charts keep missing
coordinates blank and require numeric values for coordinates that are present.

Series values accept finite numbers, numeric strings, and blanks. An invalid series
value produces `CHART205` with the series name and point index. Invalid scatter
coordinates produce `CHART208`. A failed conversion preserves the previous output.
Use `--recover` to replace an invalid series declaration with an editable diagnostic
placeholder and continue with the surrounding content.

````markdown
```chart {#fig-sales caption="Quarterly performance"}
type: column
title: Revenue and margin
categories: [Q1, Q2, Q3, Q4]
series:
  - name: Revenue
    values: [100, 120, 135, 150]
  - name: Margin
    values: [20, 24, 30, 32]
secondary_series: [Margin]
secondary_axis:
  title: Margin (%)
  min: 0
  max: 40
legend: bottom
data_labels: true
style: 10
x_axis:
  title: Quarter
y_axis:
  title: Revenue (USD)
  min: 0
  max: 200
  number_format: "0"
```
````

`legend` accepts `right`, `left`, `top`, `bottom`, `top_right`, or `none`. Secondary axes are supported for column, bar, and line charts. `secondary_axis` can independently set a title, minimum, maximum and number format. Scatter charts support numeric bounds on both primary axes.
