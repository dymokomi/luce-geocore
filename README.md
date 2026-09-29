# Luce Geocore

Shared geometry for Luce, with no GPU or UI dependency: polygon meshes, their
attributes, modeling kernels (point and face operators, subdivision, bevel, fill,
dissolve, fuse), primitives, and CPU spatial queries (a lazy triangle BVH).
Importers, CAD tessellation and editors produce and share these meshes; the
renderer in [luce-3d](https://github.com/dymokomi/luce-3d) draws them.

A result is immutable once published. Operators return new meshes and share
everything they did not change, so a snapshot or a worker-to-UI hand-off costs
no copies. See [the API](docs/API.md), [mesh modeling](docs/MESH_MODELING.md)
and [validation](docs/VALIDATION.md).

```prisma
def dependency "luce-geocore" {
    str owner = "dymokomi"
    str version = "^0.1.0"
}
```

Import `geocore` (`from geocore import PolygonMesh, MeshBuilder, Vector3`).
`geocore_growing` exports `Growing`, a heap array that keeps its capacity.

Use the compiler revisions in `bootstrap/PACKAGES`, checked out beside this
repository, and run `./test.sh`: the Base checks at native optimization levels
0–3 and in both C modes, each with allocation failure injected at every stage.

Licensed under MIT or Apache-2.0, at your option.
