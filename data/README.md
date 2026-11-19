# Complaint datasets

The canonical columns are defined in `src/data/complaints.py` and enforced by
`scripts/prepare_dataset.py`. Start with the generated file in `synthetic/`.

The initial demo has 40 synthetic examples and is not evidence about real
Jharkhand communities. It intentionally has no complaint dates, blocks,
severity labels, or affected-population estimates because the source sample
does not provide those facts. Unknown values stay blank or are labelled
`unknown`; they are not inferred.

The research target is 2,000–5,000 records. Do not treat the target as met until
records are collected from documented, licensed public datasets and/or
consent-based surveys. Never silently mix synthetic examples with real records.

## Geography reference data

`geography/jharkhand_state.geojson` contains a simplified state outline sourced
from OpenStreetMap relation
[1960191](https://www.openstreetmap.org/relation/1960191), retrieved through
Nominatim on 2026-11-05. The geometry is licensed under the Open Database
License (ODbL) 1.0. Attribute the map to **© OpenStreetMap contributors** and
see https://www.openstreetmap.org/copyright for the license terms.

This state outline is for visual reference only; it is not an official
cadastral boundary and contains no district borders or complaint locations.
