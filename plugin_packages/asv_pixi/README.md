# asv_pixi

Skeleton plugin for an **API-oriented** pixi backend (`environment_type = "pixi"`).
Not implemented yet — registers the type only after install + `"plugins": ["asv_pixi"]`,
and construction raises until bindings exist.

Do not treat this as shelling out to the `pixi` CLI; the intended path is library APIs
(similar to py-rattler / libmamba), with conda-style CLI reserved for `asv_conda`.
