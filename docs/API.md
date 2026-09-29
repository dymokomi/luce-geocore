# API

The package exports `geocore`: shared geometry with no GPU or UI dependency.
Public objects use `init` and methods in Base, and `Type(args)` construction in
Luce. Mutating or allocating operations can fail; Luce callers handle or
propagate those errors. See [immutable mesh modeling](MESH_MODELING.md) for
attribute domains, topology operators, primitive generators and BVH picking.

| Type | Responsibility and principal methods |
| --- | --- |
| `Vector3(x=0,y=0,z=0)` | Immutable operations `add`, `subtract`, `multiply_scalar`, `dot`, `cross`, `length`, `normalized`, `rotated`; public coordinates are values. |
| `Matrix4` | Affine column vectors and translation, implicit final row `(0,0,0,1)`; `compose`, `multiply`, `transform_point`, `transform_direction`, `transform_normal`. |
| `Vertex`, `Bounds`, `Geometry` | The per-vertex drawing interface a renderer consumes (luce-3d), and axis-aligned bounds. |
| `Mesh(points,sizes,corners,display=none,precise=false)` | Immutable shared-point polygon topology (the geometry core's mesh; not a per-vertex `Geometry`: renderers draw its arrays, and luce-3d's `MeshGeometry` wraps it for the per-vertex path). `vertex`/`index` give per-corner vertices and display indices. Optional validated display triangles are independent of wire edges (see below). `cube(size=2)` builds a grounded cube; `empty()` builds an empty result. `point_count`, `point`, `face_count`, `face_size`, `face_point`, `face_normal`, `face_center`, `edge_count` (fallible: edges are a lazy cache), `edge_point`, `triangle_face` expose topology. `is_precise`, `without_precision` (see storage below). |
| `Mesh.transformed(translation,rotation,scale)` | Returns a new mesh with transformed points and regenerated normals. Rotation is XYZ radians; scale must be nonsingular. Reflections reverse winding. |
| `Mesh.moved_points(selection,delta)` / `merged(other)` | Return a new displaced or concatenated mesh without modifying either input. |
| `Mesh.extruded_faces(selection,distance)` | Extrudes a face region along averaged selected-face normals. Shares new points across selected faces and adds walls only on boundary edges; cap face IDs remain stable. Requires a nonzero distance and a region boundary. |
| `Mesh.ray_face(origin,direction)` / `ray_distance(origin,direction)` | Fallible nearest two-sided intersection, or `-1`. Normalize direction for world-space distances. |
| `Mesh.surface_distance(point)` / `closest_face(point)` | BVH nearest surface distance / primitive ID; `-1` for empty geometry. Points must be finite. |
| `Mesh.prepare_queries()` | Builds the shared spatial index before first use, e.g. on a worker before handing a final viewport mesh to the UI. Idempotent and fallible; no topology change. |
| `MeshBuilder(precise=false)` | Bounded Base topology staging: `point`, `face`, `corner`, `finish`, `close`. Importers and operators share the same mesh limits. Copying a precise mesh's points makes the result precise. |
| `PolygonTopology` | Borrowed read interface for points, polygon corners and edge endpoints. Numbering/lifetime are defined by the implementation. |
| `DissolveWorkspace(source,edits=128)` | Base-only local edge-dissolve staging over a borrowed immutable `Mesh*`. `face_slots`, `active`, `neighbor`, `dissolve`, `finish`, `close`; see lifetime and ordering below. |
| `MeshOps`, `TopologyTools`, `MeshNormals`, `MeshPrimitives` | Modeling kernels returning new meshes: point/face operators, subdivision, fuse; bevel, fill, dissolve; grouped corner normals; grid, sphere, cylinder, torus. |

## Storage and precision

A mesh is structure-of-arrays, each array a shared column (`Column[T]`,
copy-on-write, with a change id): f32 positions measured from an f64 `origin`,
i32 face offsets and corner points, f32 face normals and i32 display
triangles. The origin is the bounds center when coordinates exceed 4096 or 8×
the model's size, else zero, so f32 positions keep about 1e-7 of the model's
size. Construction validates and computes normals and triangles in parallel on
the `geocore_parallel` pool (`parallel_for`, `run`, `warm`).

What connectivity alone determines (the face of each corner, the edges, numbered
by first corner in a deterministic parallel build, point-to-face incidence and
the connectivity hash) is a lazy cache shared by every mesh with that topology.
A position edit (`moved_points`, `with_positions`, rigid `placed`) copies the
positions once, recomputes only the faces around moved points, shares the
topology, its caches and every attribute, and refits the previous BVH on the
next query instead of building one.

A precise mesh also keeps its f64 points; `point`, normals, triangulation and
derived meshes use them, while display and queries use the f32 positions. B-rep
tessellation builds its chart meshes this way (trims resolve features far below
f32 spacing) and publishes `without_precision()`. Position edits of a precise
mesh rebuild it.

## Limits

Polygon meshes allow 8,388,608 points/faces, 33,554,432 corners, and 3–256 corners per
face. Their topology and triangulation are copied/owned; concave faces use ear
clipping, and degenerate input is rejected. A corner indexes a shared point;
`sizes` partitions the flattened `corners` array into ordered polygons. Empty
results are valid data but should not be submitted as renderable meshes. These
operators are CPU geometry operations. Face UVs are provisional local coordinates;
attribute contracts are detailed in MESH_MODELING.md; cross-face self-intersection
cleanup is not implemented. Attribute-only edits share immutable topology/BVH on
one thread; detached worker transfers remain independent copies.
`mesh_type` is the Base ownership descriptor.

The BVH is lazy: constructing, rendering or editing an unqueried mesh does not
build it. The first ray/distance query (or `prepare_queries`) builds and publishes
one immutable index shared by attribute snapshots. Allocation failures propagate
and leave the cache retryable, never a partial index or a false "no hit" result.
Concurrent native borrowed readers synchronize initialization; warmed queries
require no allocation or mutex. Keep the mesh alive until all readers finish.
ARC ownership and snapshot creation/destruction remain on their owning thread;
this does not make interop references transferable between threads.

Display indices address the flattened **corner** array, not shared point IDs.
Each face occupies `3*(size-2)` entries, in face order. A wholly `-1` face asks
for ordinary projected ear clipping; an explicit face must cover its oriented
boundary exactly once, pair interior edges in opposite directions, and contain
only nondegenerate triangles within that face. This is a triangulation contract,
not a CAD-support or global self-intersection validator. Geometry producers remain
responsible for checking their support, trimming and approximation error.

Rendering, picking and surface-distance queries use the same retained display
triangles. They do not add diagonals to `edge_count` or alter polygon topology.
Attribute edits, detached copies, affine placement (including reflections),
merges and unchanged-geometry subsets preserve them. Arbitrary point edits
invalidate and regenerate them. `MeshBuilder.set_last_display` takes **local**
corner indices; `copy_last_display` carries a source face through point-ID remaps
or a reversed polygon. `triangulate_last` computes a projected candidate without
allocating a mesh or BVH. Builder rollback via `nf`/`nc` also rewinds display data;
appending a replacement face clears its old display slots.

`MeshOps.compact` only removes unused point records; it preserves authored `N`
attributes, face/corner order and retained display indices. `MeshOps.faces`
with operation 0 (face filtering) also retains each surviving corner's authored
normal. Moving points or changing winding still invalidates stale normals.
`MeshBuilder.finish(source=none, preserve_normals=false)` allows geometry-preserving
operators to opt in explicitly; ordinary modeling edits retain the default.

`TopologyTools.dissolve` retains the two source faces' display triangles while
removing their shared polygon edge. The geometric surface is unchanged; the
removed edge becomes a display diagonal. A union with repeated boundary vertices
is rejected. This does not repair self-intersections already present in the input.

`DissolveWorkspace` batches up to 128 such edits without rebuilding the entire
mesh after each dissolve. Keep its source alive and immutable until `close`;
the scratch holds no managed owner and must not outlive that borrowed source.
Original edge IDs remain stable; face slots include inactive tombstones, with
each new union appended. Iterate `face_slots` in order and skip `!active(face)`.
`neighbor(face,side)` reports the other active face or -1 for an unavailable
neighbor. Nonmanifold or inconsistently oriented input cannot be dissolved.
A failed dissolve, including allocation failure during display validation, does
not change active topology and can be retried. `finish` materializes an independent
mesh in the same order, with the same display triangles and attribute provenance,
as sequential `TopologyTools.dissolve` calls. This is native single-owner scratch,
not a concurrent mutable mesh or a CAD-specific merge policy.
