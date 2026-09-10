# Offline Geo routing boundaries

Source: Natural Earth 1:10m Admin-0 Countries, version 5.1.1.
Downloaded 2026-09-10 from
https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip
SHA-256: `ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6`.

Natural Earth's terms state that all versions of its raster and vector map data
are in the public domain, including modification and electronic distribution:
https://www.naturalearthdata.com/about/terms-of-use/ (verified 2026-09-10).
Made with Natural Earth. Authors include Tom Patterson and Nathaniel Vaughn Kelso.

`ne-regions-5.1.1.json` extracts ADM0_A3 CHN, HKG, MAC and TWN multipart polygon
rings, in WGS84; coordinates are rounded to six decimals without simplification.
The repository recipe is `scripts/build_geo_boundaries.py`; it checks the archive
hash, declared version, datum, feature IDs and shape type before extraction.
The released resource hash is `25aca3d92c8b53faf03021601b344f58277577d71f6d63e3d55ea363ed6b257c`.

These generalized, de facto boundaries serve provider routing, not legal country
classification or ground truth about a media subject. A 500 m guard around the
mainland feature's boundaries (including coastlines) produces `uncertain` and no
remote query. The guard is an implementation policy, not a guarantee of positional
accuracy. Islands, reclaimed coastlines, border-near locations and disputed areas
may require better geographic evidence. No online country detection is performed.
