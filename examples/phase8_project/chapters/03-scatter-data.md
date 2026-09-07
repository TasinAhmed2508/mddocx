# Scatter and imported data

```chart {#fig-scatter caption="Latency versus accuracy"}
type: scatter
title: Accuracy by latency
source: ../data/models.json
category: Latency
series_fields: [Accuracy]
```

```data-table {#tbl-models caption="Model benchmark data"}
source: ../data/models.json
columns: [Model, Accuracy, Latency]
```

[Figure @fig-scatter] uses numeric x-values. The same JSON source is imported as the native Word table in [Table @tbl-models].
