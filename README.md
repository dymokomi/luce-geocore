# Luce Geocore

Shared geometry for Luce, with no GPU or UI dependency: polygon meshes, their
attributes, groups and selections (Houdini's group syntax), modeling verbs
(point, face and topology operators such as extrude, bevel, loop cut, clip,
mirror and spin, run through one verb framework), subdivision, primitives, and
CPU spatial queries (a lazy triangle BVH).
Importers, CAD tessellation and editors produce and share these meshes; the
renderer in [luce-3d](https://github.com/dymokomi/luce-3d) draws them.

A result is immutable once published. Operators return new meshes and share
everything they did not change, so a snapshot or a worker-to-UI hand-off costs
no copies. Besides meshes, a geometry set holds points, instances, curves
(poly, Bezier, NURBS, Catmull-Rom), sparse volumes and SDFs, and saves as a
.prism file. See [the API](docs/API.md), [curves, volumes, SDFs, set verbs and
files](docs/FAMILIES.md), [mesh modeling](docs/MESH_MODELING.md) and
[validation](docs/VALIDATION.md).

```prisma
def dependency "luce-geocore" {
    str owner = "dymokomi"
    str version = "^0.7.1"
}
```

The Code node runs per-element Luce Base snippets over a set (Houdini's Attribute
Wrangle, and with Run Over Voxels the Volume Wrangle) through
[luce-kernel](https://github.com/dymokomi/luce-kernel): `Code.check`, `Code.complete`
and `Code.hover` for the editor and `Code.run` for the cook; the API a snippet sees is in
`src/code/stubs.lucb` (with the `gsplat` helpers for splat clouds in `src/code/gsplat.lucb`),
and `tests/code` times whole cooks with `--bench`.

The Script node's API is `luce_geocore.script` (Houdini's Python SOP, in Base): a
script's `cook(k: Cook*)` builds and edits a `Geometry` (points, polygons, attributes,
groups, curves, the point cloud, instances) and runs any verb by name (`Verb`); luced-3d
builds it into a tool whose `main` calls `serve`, run in a child process the editor
drives with `ScriptProcess`. `tests/script` checks the API and the protocol end to end.

Import `geocore` (`from luce_geocore.geocore import Mesh, MeshBuilder,
Vector3`). Base code in other packages also has `luce_geocore.kernel` (bit
sets and groups, mesh assembly and its size limits, the geometry set's
component protocol, the codec registry, curves and fields),
`luce_geocore.core.shared` (shared columns) and `luce_geocore.core.growing`
(`Growing`, a heap array that keeps its capacity). A mesh's arrays as spans
(`point_span()`, `corner_span()`, …) and their packing into GPU layouts
(`pack_positions`, …) are methods of `Mesh` that only Base sees: Luce leaves
out the methods whose signatures it cannot take.

Check out the compilers and packages beside this repository, at main (`python3
../luce-base/tools/checkout_main.py . ../luce`), and run `luc test`: the module tests and the Base mesh checks
(`tests/mesh`), each with allocation failure injected at every stage.

Licensed under MIT or Apache-2.0, at your option.
