# Immutable polygon modeling

`PolygonMesh` supports point clouds and indexed polygon surfaces. A polygon's
vertices are face corners, distinct from shared spatial points. Mesh results
own topology, derived triangulation/edges/normals, numeric attributes and a
lazy triangle-BVH cache. Algorithms return new meshes; callers retain ownership
of inputs.

## Attributes

Every array of a mesh, its attributes included, is a shared column
(`core/shared.lucb`): one heap block with an atomic user count and a change id.
Snapshots, worker-to-UI transfers (`detached_mesh`) and edits share every column
they leave alone, so adding an attribute, moving points or handing a result to
another thread costs only what changes. A column is immutable once a mesh holds
it; writers copy on write (`writable()`), which also gives the copy a fresh id.
Equal ids mean equal contents on any thread: caches key on them
(`points_id`, `corners_id`, `triangles_id`, `normals_id`, `edges_id`,
`attribute_id`).

`with_attribute(name, domain, width, values, integer=false)` returns a new mesh.
Domains: points 0, corners 1, faces 2, detail 3, edges 4. Width is 1–4; flattened
values must match `domain_count(domain) * width`. Values are stored typed
(`core/attributes.lucb`): integers as i32 (i64 when out of range), other numbers
as f64, so every value reads back exactly; booleans (packed bits), i8 and f32
columns exist for Base producers. `with_single_attribute(name, domain, values)`
stores one tuple for the whole domain in O(1). Names are per-domain; P is
reserved; there is no limit on the number of attributes. Edge attributes are
indexed by edge id and follow their corners through topology changes.

Inspect with `attribute_count`, `find_attribute`, `attribute_name`,
`attribute_domain`, `attribute_width`, `attribute_integer`, `attribute_type`,
`attribute_storage`, `attribute_value`. Use `without_attribute`,
`renamed_attribute`, `promoted_attribute` for edits. Promotion averages floating
contributors and picks the first integral contributor; source attributes are
retained. Detail broadcasts to other domains. `AttributeKernels` computes whole
attributes in Base: `uv_project`, `normals`, `face_areas`, `filled` (constant or
hashed-random values) and `membership` (a 0/1 group).

`remapped` accepts point, face and corner parent maps. A parent of -1 produces
zero attributes. `with_positions` preserves attribute identity. Merge unions
compatible schemas (the wider scalar type wins), zero-fills missing data, and
preserves left detail values.
Transforms preserve generic stored values; they do not implicitly reinterpret
numeric tuples as normals or directions.

Rendering consumes Cd and uv with corner > point > face > detail precedence.
Normals used for shading are currently derived face normals, not stored N.

## Operators

- `MeshPrimitives`: grid, sphere, cylinder (including cone), torus.
- `MeshOps.faces`: operation codes delete=0, reverse=1, triangulate=2,
  individual fractional inset=3, normal-offset duplicate=4, split=5.
- `MeshOps.points`: relaxation=0, deterministic noise=1, peak=2,
  flatten Y=3, rotate XYZ radians=4, scale XYZ=5, grid snap=6.
- `MeshOps.subdivide(mesh, smooth=false)`: linear quads or Catmull–Clark;
  floating point/corner attributes interpolate, integral attributes inherit.
- `MeshOps.fuse`: selected-point spatial-hash welding, first-parent ownership.
- `MeshOps.delete_points` removes incident faces; `compact` removes unused points.
- `TopologyTools.bevel`: all-edge fractional chamfer of closed oriented meshes.
- `TopologyTools.fill`: one selected boundary loop.
- `TopologyTools.dissolve`: one selected interior edge.
- Existing mesh methods supply immutable TRS, merge, point movement and region
  face extrusion with boundary walls and attribute provenance.

No editor commands, node graph state or selection UI live in these modules.
Limits are 8,388,608 points/faces, 33,554,432 corners and 256 corners per polygon.
Attribute budgets count tuples, not scalar components. Attribute-only changes
share immutable topology and BVH; cross-thread transfers remain deep native copies.
There are at most 32 attributes with 262,144 values each. Invalid topology,
cardinality and capacity violations return checked errors.

`ray_face` and `ray_distance` use the immutable triangle BVH. They accept world
geometry-space rays; callers should normalize directions for metric distances.
Ray and distance queries can fail when first building the index. Call
`prepare_queries()` on a worker to warm a final mesh before UI handoff. Attribute
snapshots share the cache; intermediate unqueried meshes never build it. See
API.md for concurrent borrowed-reader and ownership constraints.
