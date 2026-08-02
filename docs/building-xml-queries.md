# Building CDC WONDER XML queries from scratch

This documents what we learned building queries for datasets that have no
existing templates or examples: specifically D202 (Tuberculosis), D133 (Fetal
Deaths), and D150 (Expanded Fetal Deaths).

## The XML parameter structure

A CDC WONDER XML query is a flat list of `<parameter>` elements, each with
`<name>` and `<value>`. They fall into these categories:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `B_1` through `B_5` | Group-by dimensions (what rows appear) | `B_1 = D202.V20` (Year) |
| `F_*` | Finder-stage filter for hierarchical codelists | `F_D133.V22 = *All*` |
| `I_*` | Text input companion to `F_*` (always empty) | `I_D133.V22 = ""` |
| `M_*` | Measures to include in output | `M_1 = D202.M1` (Cases) |
| `O_*` | Output options: format, precision, radio button selections | `O_age = D202.V1` |
| `V_*` | Value filters for dropdown selects | `V_D202.V20 = *All*` |
| `finder-stage-*` | Declares that a variable uses codeset mode | `finder-stage-D133.V22 = codeset` |
| Boilerplate | Required metadata fields | `dataset_code`, `stage`, `action-Send` |

## How to read `query_params_D*.json`

Each `query_params_D*.json` file in `health/data/raw/wonder/` was scraped from
the CDC WONDER request form. It contains two sections. `selects` holds every
dropdown on the form: a `name` starting with `F_` means a hierarchical
finder-stage select, and one starting with `V_` means a regular filter
dropdown. `inputs` holds the checkboxes, radio buttons, hidden fields, and
submit buttons.

### Finding required parameters

1. Group-by variables come from `selects` where `name = "B_1"`. The `value`
   field of each `option` is what you put in the XML, for example `D202.V20`
   for Year.

2. Measures come from `inputs` where `type = "input_checkbox"` and `name`
   starts with `M_`. Check `input_hidden` for `M_*` fields too, since those
   are always submitted and must appear in the XML.

3. Radio button `O_*` parameters come from `inputs` where
   `type = "input_radio"`. They are required. Omit one and CDC WONDER
   returns HTTP 500. Use the first option's `value` as a safe default.

4. Finder-stage `F_*` and `I_*` parameters come from `inputs` where
   `type = "input_hidden"` and `name` starts with `finder-stage-`. Each
   `finder-stage-D***.V##` needs four entries:
   - `F_D***.V## = *All*`, the filter select, which gets the corresponding
     `selects` entry whose `name` starts with `F_`
   - `I_D***.V## = ""`, the empty text input companion
   - `O_V##_fmode = freg`, which tells WONDER to use regular filter mode
   - `finder-stage-D***.V## = codeset`, which declares codeset mode

## The radio button trap

This is the number one cause of HTTP 500 errors when building new queries.

CDC WONDER's response when radio buttons are missing:

```
<message>To Group Results By {0} you must also select the {1} button where found below section #1.</message>
```

The `{0}` and `{1}` are unfilled Java template placeholders. CDC's error
rendering is broken, so you won't know *which* radio group is missing. Each
occurrence of this message in the response corresponds to one missing radio
button group.

To fix it, find all `input_radio` elements in the dataset's `query_params`
JSON and include one value per group:

```python
import json
f = json.load(open('query_params_D133.json'))
for i in f['parameters']['inputs']:
    if i['type'] == 'input_radio':
        print(i['name'], i['value'], i.get('label'))
```

Use the first `value` for each `name` group as the default. Common ones:

| O_ name | Purpose | Default pattern |
|---------|---------|-----------------|
| `O_age` | Which age grouping variable to use | First radio value (e.g., `D133.V1`) |
| `O_location` | Which geographic level to use | Standard states (e.g., `D133.V21`) |
| `O_xlocation` | Expanded geography variant | First option (e.g., `D133.V61`) |
| `O_expanded` | Standard (`S`) vs expanded (`X`) race data | `S` |
| `O_hispanicity` | Which Hispanic origin variable | First option |
| `O_race` | Which race classification | First option |
| `O_gestation` | Which gestational age grouping | First option |
| `O_weight` | Which birth weight grouping | First option |
| `O_birthplace` | Which delivery place grouping | First option |
| `O_icd` | ICD code set (for cause-of-death datasets) | `D150.V107` (ICD-10) |

## What M_* (measures) to include

Always check the `input_hidden` entries in the `inputs` list. The HTML form
submits these automatically, so the XML has to mirror them:

```
M_1 type=input_hidden value=D202.M1
M_2 type=input_hidden value=D202.M2
```

They are mandatory. If the hidden field sends `M_2 = D202.M2`, your XML needs
`<M_2>D202.M2</M_2>` even if you didn't explicitly choose that measure. You
can add further measures by including the checkbox `M_*` values.

## Minimum required boilerplate

Every query needs these at the end:

```xml
<parameter><name>action-Send</name><value>Send</value></parameter>
<parameter><name>dataset_code</name><value>D202</value></parameter>
<parameter><name>dataset_label</name><value>OTIS TB Data 1993-2023</value></parameter>
<parameter><name>stage</name><value>request</value></parameter>
```

Some datasets also need `dataset_vintage_latest`. D202, for instance,
requires `<value>TB</value>`. Check the `input_hidden` list.

## Rate limiting

CDC WONDER enforces a 15-second minimum gap between API requests. Running two
queries back to back returns HTTP 429:

```
Request rate exceeded. To protect system resources, API/XML requests must have
at least 15 seconds between consecutive requests.
```

Wait at least 15 seconds between `pulse run` calls when testing.

## Example: minimal TB query (D202)

The simplest working query for "TB cases by year" needs:

1. `B_1 = D202.V20` (group by Year)
2. `B_2` through `B_5 = *None*`
3. `M_1 = D202.M1`, `M_2 = D202.M2` (mandatory hidden measures), `M_3 = D202.M3` (rate, optional but useful)
4. `O_age = D202.V1`, `O_race = D202.V16` (radio buttons, required)
5. All `V_D202.V*` filters set to `*All*`
6. Boilerplate: `dataset_code = D202`, `dataset_label`, `stage = request`, `action-Send = Send`

D202 has no finder-stage variables, so it needs no `F_*` or `I_*` entries.

## Example: fetal deaths by cause (D150)

D150 is the most complex of the three: 91 group-by options, 9 radio button
groups, 5 finder-stage variables. Beyond what D133 needs, it also wants:

- `F_D150.V107 = *All*` plus `I_D150.V107 = ""` plus `finder-stage-D150.V107 = codeset` plus `O_V107_fmode = freg`, the ICD cause-of-death codeset
- `O_icd = D150.V107` to select ICD-10 codes rather than 124 Selected Causes
- the `O_urban`, `O_delivery`, `O_prenatal2`, and `O_m_hispanicity` radio groups

When grouping by `D150.V107-level1` (ICD Chapter), the `O_icd = D150.V107`
radio button is what tells WONDER to use the ICD-10 codeset for that
dimension.

## Workflow for a new dataset

1. Find the `query_params_D***.json` file in `health/data/raw/wonder/`
2. Extract group-by options: `selects` where `name = "B_1"`
3. Extract mandatory measures: `inputs` where `type = "input_hidden"` and `name` starts with `M_`
4. Extract required radio buttons: `inputs` where `type = "input_radio"`, one per group
5. Extract finder-stage variables: `inputs` where `type = "input_hidden"` and `name` starts with `finder-stage-`
6. Build the V_* filter list from `selects` where `name` starts with `V_` (set all to `*All*`)
7. Build the F_* list from `selects` where `name` starts with `F_` (set all to `*All*`)
8. Add boilerplate: `dataset_code`, `dataset_label`, `stage`, `action-Send`
9. Test, and watch for HTTP 500 with unfilled `{0}` placeholders (missing radio buttons)
