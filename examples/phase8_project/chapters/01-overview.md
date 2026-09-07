# Overview

This acceptance report validates native editable Office charts in mddocx {{ release }}.

```chart {#fig-revenue caption="Quarterly revenue and profit"}
type: column
title: Quarterly performance
source: ../data/quarterly.csv
category: Quarter
series_fields: [Revenue, Profit]
```

The first native chart is shown in [Figure @fig-revenue].

```chart {#fig-units caption="Units by quarter"}
type: bar
title: Units sold
source: ../data/quarterly.csv
category: Quarter
series_fields: [Units]
```

[Figure @fig-units] exercises horizontal bars.
