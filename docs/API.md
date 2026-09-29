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
| `Mesh.ray_face(origin,direction)` / `ray_distance(origin,direction)` | Fallible nearest two-sided intersection, or `-1`. Normalize direction for world-space distances. |
| `Mesh.surface_distance(point)` / `closest_face(point)` | BVH nearest surface distance / primitive ID; `-1` for empty geometry. Points must be finite. |
| `Mesh.prepare_queries()` | Builds the shared spatial index before first use, e.g. on a worker before handing a final viewport mesh to the UI. Idempotent and fallible; no topology change. |
| `MeshBuilder(precise=false)` | Bounded Base topology staging: `point`, `face`, `corner`, `finish`, `close`. Importers and operators share the same mesh limits. Copying a precise mesh's points makes the result precise. |
| `PolygonTopology` | Borrowed read interface for points, polygon corners and edge endpoints. Numbering/lifetime are defined by the implementation. |
| `DissolveWorkspace(source,edits=128)` | Base-only local edge-dissolve staging over a borrowed immutable `Mesh*`. `face_slots`, `active`, `neighbor`, `dissolve`, `finish`, `close`; see lifetime and ordering below. `dissolve_edge(source, edge)` is the one-edit form. |
| `GeometrySet` | A node's result: typed components, at most one per family (`mesh`, `points`, `instances`, and families other packages register, such as luce-cad's `cad`). Immutable; copies share every column. `of_mesh`, `mesh`, `with_mesh`, `with_instance(set, translation, rotation, scale, visible)`, `instance*`, `with_cloud_of(mesh)`, `cloud_*`, `merged`, `transformed`, `realized` (every polygon, instances baked, in one pass), `blasted(paths, keep)`, `paths`, `bounds`, `footprint` (shared arrays once), `description`. |
| Groups and text | `with_group(name, domain, members)`, `attribute_group`, `group_size`, `find_edge(a, b)`; text attributes (`with_text`, `with_text_values`, `attribute_text`, `attribute_string*`) store an i32 per element into a shared string table. |
| `without_faces(faces, keep)` / `compacted()` | A face subset gathered in parallel: kept faces keep corners, triangles, normals and attributes; unused points go. `compacted` keeps every face and drops only unused points. |
| `Verbs`, `MeshNormals`, `MeshPrimitives` | Every modeling operation is a verb (see Verbs below); grouped corner normals; grid, sphere, cylinder, torus. |

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

`compacted` only removes unused point records; it preserves authored `N`
attributes, face/corner order and retained display indices, as `without_faces`
does for the faces it keeps. Moving points or changing winding (verbs) drops
stale normals.
`MeshBuilder.finish(source=none, preserve_normals=false)` allows geometry-preserving
operators to opt in explicitly; ordinary modeling edits retain the default.

`dissolve_edge` retains the two source faces' display triangles while
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
as sequential `dissolve_edge` calls. This is native single-owner scratch,
not a concurrent mutable mesh or a CAD-specific merge policy.

## Groups, text and roles

A group is a boolean attribute flagged as a group, on the point, corner,
face or edge domain; its bits are the members, 64 to a word. Edges are
numbered by connectivity, so an edge group is exact while the topology is;
its durable form is the point pairs of its edges (`edge_pairs`,
`edge_bits_from_pairs` in `geocore_kernel`). Through topology changes an
output edge continues an old edge when its two corners' parents are
neighbours in an old face; wall sides and other new edges start empty.

Text attributes hold an i32 per element into a string table, one shared
column. CAD tessellation writes each face's B-rep path to the face text
attribute `path`, which `GeometrySet.paths` and `blasted` read.

Every attribute has a role (after Houdini's type info): `N` is a normal,
`Cd` a color, `uv` a texture coordinate, `v` and `up` vectors, `id` and
`class` indices. Concatenation turns normals and vectors with their part.

## Geometry sets

`GeometrySet` components are described by a `ComponentType`, a table of
functions over the component's data (share, close, size, bytes, bounds,
placed, joined, paths, filtered, describe), so the container never
downcasts and a package adds a family without touching geocore. Putting a
component registers its type. Instances hold other sets under a
translation, rotation and scale; placing instances wraps them in one
instance, so any composition stays exact. `realized` concatenates every
mesh placed by its instance matrices in one parallel pass (`concatenated`);
a family without polygons (CAD) makes it fail with what to do instead.

Base code in other packages uses `geocore_kernel`: bit sets, string tables,
path filters, `MeshPart`/`concatenated`, `kept_faces`, groups' edge pairs,
and the component protocol (`set_find`, `set_put`, `set_remove`,
`set_storage`, the built-in families). Import its names with
`from geocore_kernel import …`: a qualified call of a re-exported function
value does not compile (reported to the compiler owners).

## Group expressions and selections

Group parameters and stored selections use Houdini's group syntax (22.0):
numbers, ranges with steps (`0-100:2`, `0-100:1,3`, open `12-`), names and
globs (`top`, `arm*`, `{arm* ^arm3*}`, `?*`), `!`, `^` and `&`, attribute tests
(`@P.y>0`, `@Cd[2]<0.5`, `@id=1,2,90`, `@id="0-4 78"`, `@name=piece*`,
`@flags&4`, `@ptnum<100`, `@primnum`, `@elemnum`) and edge forms (`p3`,
`p3-4`, `p3-4-5`, `7e2`, and on an edge target a number names a face's
edges). Our functions, which cannot clash with group names: `grow(x, n)`,
`shrink(x, n)`, `border(x)`, `connected(x)`, `loop(x)`, `ring(x)` and
`convert(x, n)` (n = 0: all related elements, 1: any). `groups/program.lucb`
states the grammar, and `tests/group_language_checks.lucb` checks every row of
Houdini's table.

An expression compiles once and evaluates to bits in Base: ranges are word
fills, names share their group's bits, `@` tests run in parallel, and edge
forms, conversions and the functions use lazy connectivity caches shared by
every mesh with the same topology (edges, and point-face, point-edge and
edge-corner lists). Results are cached process-wide by the expression and the
change ids of everything they could read. Numbers that name no element match
nothing (as in Houdini) and are counted; names found only on another domain
are converted (a face is in a point group when all its points are).

`Selection` is the Luce-side selection: bits over one domain with the
connectivity hash they index. `Selection.of(mesh, expression, domain)`,
`count`, `contains`, `next`, `changed` (add, remove, toggle, only),
`filled`, `inverted`, `combined`, `walked` (grow, shrink, border, flood,
loop, ring), `on_domain`, `points`, `center`, `fits` and `expression`, the
encoder: runs (`0-5 12`), strides (`1-9:2`), a group's name when the bits are
exactly its members, and edges as chained point pairs (`p3-4-5`), all read back
to the same bits. `Groups.with_group` makes a flagged group from an
expression, `Groups.count` counts one, and `Groups.check` returns a syntax
error or "".

## Verbs

Every modeling operation is a verb (after Houdini's SOP verbs): a Base kernel
that takes the input mesh, its group as bits on the verb's domain and the
parameter values, and returns new positions (Transform Components, Smooth,
Mountain, Peak, Flatten, Snap: topology, triangles and attributes shared), a
topology built with parents (`TopologyBuilder`), or a finished mesh. `Verbs.run`
resolves the group (empty: everything; Group Type 0 guesses the domain from
the expression's named groups), converts it to the verb's domain, cooks, and
carries every attribute and group through the parents (`propagate.lucb`:
copy one parent; mix weighted parents, AND for groups; zero for new elements;
edges by corner adjacency). The result (`VerbResult`) has the mesh, the output
selection and a warning. `Verbs.count`, `name`, `category`, `description`,
`domain` and `parm_*` describe the verbs, and luced-3d generates its node
catalog from them.

The modeling verbs, after Houdini's SOPs and Blender's tools:

- **PolyBevel** (edges): strips offset a constant distance into the faces
  beside each interior edge, 1–64 segments along a profile, overlap clamping,
  one patch face per corner hole; a lone edge's end vertex stays and its strip
  fans around it.
- **PolyExtrude** (faces or edges): regions or individual faces, with an inset
  across the region boundary and wall divisions; one front point per run of
  faces around a boundary point; a closed surface moves out. Edges extrude into
  quads (outward in the face plane on a boundary) and select their front edges.
- **Inset** (faces): the rim moves in by a distance, with a depth, as regions
  or one by one, clamped to half the boundary edges.
- **Loop Cut** (edges): loops across the quads of each edge ring, with cuts and
  slide; other faces on a ring take the new points.
- **Bridge** (edges): boundary loops or runs, paired by nearness, joined by rows
  of quads (same edge counts) or zipped with triangles.
- **Merge Points**: at the center, first, last, per island or by distance.
- **Fill**: one face per boundary loop, or a fan around a center point.
- **Dissolve** (edges, points, faces strictly): one face per joined region;
  points left between two edges go.

New corners inside a face blend that face's corners (the builder's mixed
corners), so UVs follow insets, slides and cuts; every other attribute and
group follows the parents. A verb with nothing to do, or a result with
degenerate faces, passes its input through with a warning. Edge output
selections are named by point pairs (`TopologyBuilder.select_edge`) and found
on the result.

Faces a builder copies keep their triangles (CAD cut cells survive); runs of
untouched faces copy in one pass (`copy_faces`), and only new faces are ear
clipped. `tests/bench/run.py --base <luce-base>` times every verb on the 837×837
grid (one `--native --opt 3` run each, connectivity caches warm, output mesh
and attributes included):

| Verb run | Time | Faces out | Warning |
|---|---:|---:|---|
| Transform Components, 1k faces | 21.9 ms | 700,569 |  |
| Smooth, everything | 24.5 ms | 700,569 |  |
| Delete, 1k faces | 9.7 ms | 699,569 |  |
| Reverse, 1k faces | 20.8 ms | 700,569 |  |
| Triangulate, half | 65.1 ms | 1,050,570 |  |
| Duplicate, 1k faces | 20.5 ms | 701,569 |  |
| Subdivide, everything to 2.8M faces | 662.5 ms | 2,802,276 |  |
| Fuse, 1k faces' points | 43.5 ms | 700,569 |  |
| PolyExtrude, 1k faces as a region | 29.4 ms | 702,247 |  |
| PolyExtrude, 1k faces one by one, inset, 2 divisions | 35.1 ms | 708,569 |  |
| PolyExtrude, 100k faces as a region | 53.5 ms | 702,483 |  |
| PolyExtrude, 3 edges | 50.4 ms | 700,572 |  |
| Inset, 1k faces as a region | 32.5 ms | 702,247 |  |
| Inset, 100k faces as a region | 54.1 ms | 702,483 |  |
| PolyBevel, 1k faces' inner edges | 63.5 ms | 705,242 |  |
| PolyBevel, 100k faces' inner edges, 3 segments | 453.8 ms | 1,400,093 |  |
| PolyBevel, every edge (1.4M) | 1095.2 ms | 2,798,929 |  |
| Loop Cut, one ring of 837 quads | 51.7 ms | 701,406 |  |
| Loop Cut, every ring both ways | 420.5 ms | 1,401,138 |  |
| Bridge, two facing 837-edge loops, 4 divisions | 35.6 ms | 703,080 |  |
| Merge Points, a face's points at their center | 43.6 ms | 700,568 |  |
| Merge Points, 250 pairs as islands | 45.8 ms | 700,569 |  |
| Dissolve, 250 edges between face pairs | 60.9 ms | 700,278 |  |
| Dissolve, 250 points | 52.0 ms | 699,821 |  |
| Fill, a 22-edge hole | 22.2 ms | 700,560 | Some boundary runs in the group are not closed simple loops and were left open |
| Fill, a 22-edge hole as a fan | 22.2 ms | 700,581 | Some boundary runs in the group are not closed simple loops and were left open |
| Split, 1k faces | 19.7 ms | 700,569 |  |
| Clean, everything | 28.5 ms | 700,569 |  |
