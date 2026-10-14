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
| `Mesh.query_index()` | The shared triangle BVH (`TriangleIndex`: `nearest`, `nearest_within`, `ray`) for kernels that query it many times; positions relative to `position_origin()`. |
| `Mesh.prepare_queries()` | Builds the shared spatial index before first use, e.g. on a worker before handing a final viewport mesh to the UI. Idempotent and fallible; no topology change. |
| `MeshBuilder(precise=false)` | Bounded Base topology staging: `point`, `face`, `corner`, `finish`, `close`. Importers and operators share the same mesh limits. Copying a precise mesh's points makes the result precise. |
| `PolygonTopology` | Borrowed read interface for points, polygon corners and edge endpoints. Numbering/lifetime are defined by the implementation. |
| `DissolveWorkspace(source,edits=128)` | Base-only local edge-dissolve staging over a borrowed immutable `Mesh*`. `face_slots`, `active`, `neighbor`, `dissolve`, `finish`, `close`; see lifetime and ordering below. `dissolve_edge(source, edge)` is the one-edit form. |
| `GeometrySet` | A node's result: typed components, at most one per family (`mesh`, `points`, `instances`, and families other packages register, such as luce-cad's `cad`). Immutable; copies share every column. `of_mesh`, `mesh`, `with_mesh`, `with_instance(set, translation, rotation, scale, visible)`, `instance*`, `with_cloud_of(mesh)`, `cloud_*`, `merged`, `transformed`, `realized` (every polygon, instances baked, in one pass), `blasted(paths, keep)`, `paths`, `bounds`, `footprint` (shared arrays once), `description`. |
| Groups and text | `with_group(name, domain, members)`, `attribute_group`, `group_size`, `find_edge(a, b)`; text attributes (`with_text`, `with_text_values`, `attribute_text`, `attribute_string*`) store an i32 per element into a shared string table. |
| `without_faces(faces, keep)` / `compacted()` | A face subset gathered in parallel: kept faces keep corners, triangles, normals and attributes; unused points go. `compacted` keeps every face and drops only unused points. |
| `Verbs`, `MeshNormals`, `MeshPrimitives` | Every modeling operation is a verb (see Verbs below); grouped corner normals; grid, box, sphere, cylinder, torus standing on the origin (the primitive verbs have every option). |

## Storage and precision

A mesh is structure-of-arrays, each array a shared column (`Column[T]`,
copy-on-write, with a change id): f32 positions measured from an f64 `origin`,
i32 face offsets and corner points, f32 face normals and i32 display
triangles. The origin is the bounds center when coordinates exceed 4096 or 8×
the model's size, else zero, so f32 positions keep about 1e-7 of the model's
size. Construction validates and computes normals and triangles in parallel on
luce-std's process-wide `parallel` pool.

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

Polygon meshes allow 8,388,608 points/faces and 33,554,432 corners. A face has
three or more corners and no other size limit: an n-gon of thousands of
corners (an imported cap, a dissolved region, a filled hole) stays one face
through construction, the builders, position edits, the verbs and the codec;
nothing triangulates it away. Their topology and triangulation are
copied/owned; concave faces use ear clipping. Faces of up to 256 corners are
clipped by scanning for ears in the face's plane (with an exact partition
when greedy ears strand a trim chain); larger faces are clipped on a linked
ring in about linear time: only reflex corners are tested, through a grid
over the face, and clipping goes on from the last ear instead of starting
over (a 20,000-corner circle takes about 1.5 ms, a 5,000-corner comb of thin
teeth about 25 ms). Per-face scratch lives on the stack for faces of up to
256 corners and on the heap for larger ones, so running out of memory is the
only way a large face can fail. A face is never rejected for its shape: a
self-intersecting or folded
face that ear clipping cannot finish gets a fan as its display, and a face
without an area (coincident or collinear points) is kept with a zero normal and
zero-area display triangles. Repeated consecutive corners (a collapsed edge)
are still invalid topology. Modeling verbs that would make new faces without
an area pass their input through with a warning. A corner indexes a shared point;
`sizes` partitions the flattened `corners` array into ordered polygons. Empty
results are valid data but should not be submitted as renderable meshes. These
operators are CPU geometry operations. Face UVs are provisional local coordinates;
attribute contracts are detailed in MESH_MODELING.md; cross-face self-intersection
cleanup is not implemented. Attribute-only edits share immutable topology/BVH;
a detached worker transfer (`detached_mesh`) shares the immutable columns and
caches through atomic counts, and the receiver adopts it on its own thread.
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
only nondegenerate triangles within that face (any triangles, for a face
without an area). This is a triangulation contract,
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
mesh after each dissolve; joined faces may have any number of corners (its
storage grows past the room made up front for faces of up to 256). Keep its source alive and immutable until `close`;
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

## Subdivision as a display attribute

The Subdivision verb writes detail attributes only (`subd.scheme`: 1
Catmull-Clark, 2 Loop, 3 bilinear; `subd.level`, `subd.render_level`,
`subd.boundary`); downstream nodes keep reading the cage. The Crease verb sets
the edge attribute `crease` (USD sharpness: 10 infinitely sharp, s sharp for s
levels, fractions blending); `corner_sharpness` on points pins corners.

`Subdivision.display(mesh)` is the mesh the viewport draws: the cage refined
`subd.level` times (clamped to 8M faces) and taken to its limit surface, with
limit normals as point `N` (zebra and curvature read them) and `.cage_face` on
each face. Its plan (each level's refined connectivity with the cage's
attributes carried, and each level's sharpness) is built once per
connectivity, settings, sharpness and attribute columns, and kept in the
cage's topology cache (`TopologyCache.extension_of`), so every mesh with that
connectivity shares it. A Move re-evaluates only what the moved points reach
at each level and the limit around it, on the previous display mesh (its
columns change in part); an unchanged mesh is a lookup. luce-3d's renderer
draws a subdivided cage's display surface with the cage's wires over it and
maps a cage face selection onto the display faces; luced-3d's worker makes the
display before publishing, so the renderer finds it cached.

On the 700k-face grid (display level 1, 2.8M faces): plan and first
evaluation 1.3 s, a Move of 1k faces 36 ms, an unchanged mesh 0.005 ms.

## Groups, text and roles

A group is a boolean attribute flagged as a group, on the point, corner,
face or edge domain; its bits are the members, 64 to a word. Edges are
numbered by connectivity, so an edge group is exact while the topology is;
its durable form is the point pairs of its edges (`edge_pairs`,
`edge_bits_from_pairs` in `luce_geocore.kernel`). Through topology changes an
output edge continues an old edge when its two corners' parents are
neighbors in an old face; wall sides and other new edges start empty.

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
instance, so any composition stays exact. Rows may carry attributes on the
point domain, as Houdini's packed points do (`Instances.store`,
`put_attribute`, `row_text`; `instance_path` in Luce reads a row's `path`,
its place in the scene it came from); shares, joins, filters and the codec
keep them, and rows added later take zero or "". `realized` concatenates every
mesh placed by its instance matrices in one parallel pass (`concatenated`);
a family without polygons (CAD) makes it fail with what to do instead.

Base code in other packages uses `luce_geocore.kernel`: bit sets, string
tables, path filters, mesh assembly and its size limits,
`MeshPart`/`concatenated`, groups' edge pairs, and the built-in families; the component protocol itself is `GeometrySet`'s
`find`, `put`, `remove`, `storage` and `component`, which Luce does not see.
Import its names with `from luce_geocore.kernel import …`, or the module
itself (`from luce_geocore import kernel`, `kernel.set_mesh(&set)`).

## Group expressions and selections

Group parameters and stored selections use Houdini's group syntax (22.0):
numbers, ranges with steps (`0-100:2`, `0-100:1,3`, open `12-`), names and
globs (`top`, `arm*`, `{arm* ^arm3*}`, `?*`), `!`, `^` and `&`, attribute tests
(`@P.y>0`, `@Cd[2]<0.5`, `@id=1,2,90`, `@id="0-4 78"`, `@name=piece*`,
`@flags&4`, `@ptnum<100`, `@primnum`, `@elemnum`) and edge forms (`p3`,
`p3-4`, `p3-4-5`, `7e2`, and on an edge target a number names a face's
edges). Our functions, which cannot clash with group names: `convert(x, n)`
(n = 0: all related elements, 1: any) and every select rule's function
(Select, below): `rule(x, a, b, …)` runs the rule on group `x` with its
parameters in order (`grow(x, 2)`, `loop(p3-4)`, `sharp(*, 30)`,
`sides(*, 4, 3)`, `path(0 24, 1)`, `similar(5, 1)`, `nonmanifold(*)`). A rule
of another component type reads `x` on its own first level and its result is
converted (`sides(*, 4)` on points: the points of quads). `groups/program.lucb`
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
`count`, `contains`, `next`, `changed` (add, remove, toggle, only; sets the
active element, the one picked last: `active`, `with_active`), `filled`,
`inverted`, `combined` (with an expression), `joined` (with a selection),
`ruled` (a select rule by its verb's name: `ruled(mesh, "Select Loop", [])`),
`on_domain`, `points`, `center`, `fits` and `expression`, the
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

A verb also says how it is offered as a modeling tool, and luced-3d builds
its tool registry from that alone, so a verb added to `makers` reaches the
node menu, the Edit Mesh tools, the menus, the marking menus, the
right-click menu and the generated tool docs with no other edit:
`label` ("Bevel" for PolyBevel), `section` (Create, Modify or Select; empty
for a node only, such as Transform Components), `family` (the group menus
list it under), `icon` (a luciaos-assets name), `picks` (`PickSpec`: what it
works on, the selection levels it is picked at, as `objects points edges
faces`, and the prompt while it waits; none declared is one pick at every
level), `drag` (the parameter a drag in the viewport sets after it runs),
`gesture` (`stroke` for Bisect's line, `place` for PolyDraw's clicked
corners, `hover` for Loop Cut's ring, `knife` for the Knife's points,
`create` for a primitive drawn in the viewport, `pen` for Poly Pen)
and `whole` (with nothing selected it runs on everything). `inputs` is a
node's inputs: 0 for a primitive (no group; as an Edit step it adds to the
edited mesh), 2 for a verb that reads a reference surface second
(`VerbInput.reference`; `second_required` when it cannot do without one).
A primitive's `place` (`PlaceSpec`) names the rows the viewport's
interactive creation sets: its base (`rect` corner to corner, or `radius`),
its rise (`height` along Up, or `radius` off the base's circle), Position
and Up; `Verbs.place_*` read it and `Verbs.placement_axis(up, degrees,
axis)` gives the frame a base is drawn in. A parameter with
`bar` off stays off the tool's bar (numbers a gesture records). `Verbs.label`,
`section`, `family`, `icon`, `pick_*`, `drag`, `gesture`, `whole` and
`parm_bar` read them. A `native` verb keeps the group on its own domain,
whichever it is (the Select verbs). `Verbs.frame(name, mesh, group,
group_type, numbers)` measures where a drag of the verb stands: the group's
center, its average normal and a slide's rails; `Verbs.frame_at(center,
axis)` is a frame of a center and an axis alone, for a tool that is no verb
(luced-3d's CAD tools, measured on their own geometry).

`Verbs.run(name, mesh, group, group_type, numbers, symmetry=0, keep=false, second="", reference=none)`
also carries the Edit engine's options: `symmetry` (1..3) adds the mirror of
every group member across the X, Y or Z plane through the origin, and `keep`
makes the output selection the group carried through the verb instead of what
it made. Transform Components' Soft radius and Falloff move the points near
the group by a weight (1 in the group, falling off with the distance to its
nearest member); `selection_weights` in `luce_geocore.kernel` computes the same
weights for a selection, which the Edit viewport tints points by.

The modeling verbs, after Houdini's SOPs and Blender's tools:

- **PolyBevel** (edges or points): Blender's bevel, its algorithm read and
  written our own way in `verbs/bevel*.lucb` (the files' notes describe it).
  Width measured as Offset, Width, Depth, Percent or Absolute; 1–64 segments
  along a superellipse profile (Shape 0.5 round, 0.25 chamfer, 1 square, 0
  hollow; points by equal chords) or a Custom profile ramp; corners where
  beveled edges meet filled by a Grid Fill patch (Catmull-Clark with Sabin's
  center rule; the cube corner an octant of the superellipsoid) or Cutoff
  faces; outer miters Sharp, Patch or Arc and inner Sharp or Arc with Spread;
  Clamp overlap, Loop slide with the even-widths pass, Harden normals (N on
  corners), Mark seams and sharp, face_strength, Material, and the Angle or
  Weight limit (`bevel_weight` on edges or points, set by the **Bevel
  Weight** verb). Affect Vertices cuts points off. Corner values are
  interpolated by mean value coordinates in the face each corner lies in.
  Edges with three or more faces, and bevel vertices whose faces are not one
  fan, refuse the run; boundary edges are left. Its keys (Blender's A, P, S,
  M, V, O, I, Z, N, C, H, U, K, L) are `Verb.keys`, which luced-3d's drag
  reads. Every stage runs in parallel but numbering the bevel vertices and
  walking the even-widths chains: the output is built in pieces (ranges of
  faces, edges and vertices), each into its own `FaceBatch`, joined in order
  by `append_batches` (`verbs/face_batch.lucb`), so the mesh is the same on
  any number of threads.
- **PolyExtrude** (faces or edges): regions or individual faces, with an inset
  across the region boundary and wall divisions; one front point per run of
  faces around a boundary point; a closed surface moves out. Edges extrude into
  quads (outward in the face plane on a boundary) and select their front edges.
- **Inset** (faces): the rim moves in by a distance, with a depth, as regions
  or one by one, clamped to half the boundary edges.
- **Loop Cut** (edges): loops across the quads of each edge ring, with cuts and
  slide; other faces on a ring take the new points.
- **Bridge** (edges, or faces whose outlines it bridges and removes):
  boundary loops or runs paired by nearness, or each first-pick chain with
  the nearest chain of the second pick (`Verbs.run`'s `second`); joined by
  Cuts + 1 rows of quads (same edge counts) shaped Linear, Blend path (a
  cubic Bézier between the loops' centers, handles Blender's length: half
  the gap across the normals' plane times 4/3 down to 3/4; each loop's shape
  carried along it without twisting; a straight run square to itself)
  or Blend surface (each point's own Bézier leaving the faces), with a
  Profile swell of six shapes; Twist; Merge welds the loops at Merge factor
  instead. Runs of different lengths zip with triangles.
- **Grid Fill** (edges): each closed hole of an even number of boundary
  edges filled with a quad grid, Span edges by n/2 - Span from its sharpest
  corner (Offset moves it; Span 0 finds the next corner, else a quarter),
  inner points on the Coons patch of the four sides (Simple: the first and
  third only).
- **Solidify** (faces): a shell Thickness thick, Offset placing it behind,
  centered or in front, Even thickness by each point's mean 1/cos, Fill rim
  along the group's outline, Flip; Clamp and Angle clamp as the Blender
  modifier's (a point's move held to Clamp × its shortest edge).
- **Poke** (faces): each face a fan round a new point at its weighted mean,
  mean or bounds center, moved Offset (Relative: times its mean radius)
  along its normal.
- **Rotate Edge** (edges): each edge turned one corner on (or back) within
  its two faces.
- **Edge Split** and **Rip** (edges, Rip also points): the surface cut open
  by sectors round each point; Rip carries a chain end inside the surface
  one edge on (Blender's rule), moves one side Offset into its faces (Flip
  for the other) and with Fill closes the gap; a ripped point splits its fan
  along two opposite edges (Turn picks which).
- **Separate** (faces): the group, or each of its loose parts, a piece of its
  own: own points where it touched others, its path suffixed .001, .002, …
- **Dissolve**'s Clean points, **Delete Edge Loop** and **Limited Dissolve**:
  points left between two edges go; a loop's faces either side join and its
  points go; faces flatter than Angle join flattest first while the regions'
  area-weighted normals stay within it, straight-run points go (Boundaries,
  delimits for sharp, seams, materials, UVs).
- **Collapse** (edges, faces): each island to its center. **Merge Points**
  gains At point. **Target Weld** (points): the group onto the second
  pick's point.
- **Knife** (faces; a stroke's points after its parameters, `trailing`):
  each segment cuts with the ribbon its points sweep along the stroke's
  direction, through every face (Cut through) or the faces facing it that
  nothing hides; paths across faces split them, ends inside a face trimmed
  back, neighbors take the cut points. **Clip** is the editor's Bisect.
- **Spin** gains Flip; **Screw** (edges): Turns of Steps copies rising Rise
  each turn.
- **Symmetrize** (faces): points within Threshold of the plane moved onto it,
  the faces cut on it (Clip), one half deleted and the other mirrored,
  welded on the plane. **Snap to Symmetry** (points): each point paired
  with the point nearest its mirror within Threshold, the pair placed
  Factor between, centered points onto the plane.
- **Subdivide** on a selection (faces, or edges and the faces they close):
  only they split, the faces around kept joined with Blender's Straight Cut
  (a midpoint corner, two cut edges joined across, a quad's three as
  `quad_3edge`); Catmull-Clark moves only points all of whose faces split.
  Its Smoothness: Linear's new points onto the sphere the
  corners' normals describe. **Smooth**: Keep volume (Taubin's λ|μ), Keep
  boundary, Axes. **Relax**: the move along the surface only.
- **Triangulate**'s quad methods (Beauty, Fixed, Alternate, Shortest,
  Longest) and n-gon methods (Beauty: Delaunay flips; Clip). **Tris to
  Quads** (`Quadrangulate`): triangle pairs within Face and Shape angles
  joined squarest first, candidates priced in parallel.
- **Decimate** (`PolyReduce`): Collapse by Garland–Heckbert quadrics (outline
  planes weighted, flips and link refusals, ties to the shortest edge, Lock
  boundary), Un-subdivide by labeling the quads as a subdivision made them,
  Planar as Limited Dissolve.

A verb of two picks declares a second `PickSpec`; `Verbs.run(..., second)`
reads that pick's group on the first's group type and converts it to the
pick's domain (`VerbInput.second`), and `Verbs.wants_second` says whether the
first pick alone still wants it (Bridge with one loop, Target Weld always),
so the editor asks for it.
- **Merge Points**: at the center, first, last, per island or by distance.
- **Fill**: one face per boundary loop, or a fan around a center point;
  loops of any length.
- **Dissolve** (edges, points, faces strictly): one face per joined region,
  of any size; points left between two edges go. A region with a hole or a
  pinch is left as it was, with a warning.
- **Clip** (faces): cut by an axis-aligned plane (optionally through the
  group's centroid) or any plane given by a point and a normal (the editor's
  knife stroke), and keep the side above, below, or both (a knife cut);
  one cut point per crossed edge, which neighbors outside the group take
  into their boundaries; a face on the plane counts as above, once.
- **Connect** (edges or points): two of the group's points across a face
  split it along their diagonal; the group's edges get a point each and a
  face with two of them splits between them.
- **Edge Slide** (edges): each point of the group's chains moves along the
  edge beside it that leans most to one side of the chain.
- **PolyMirror** (faces): the group reflected across an axis-aligned plane,
  wound outward, welded to the original on the plane, with or without the
  original.
- **Spin** (edges): the group's chains swept round an axis in steps into a
  surface of revolution (a full turn closes; points on the axis stay single).
- **PolyDraw** (points): one new polygon, of any number of corners. With
  Corners > 0, that many drawn
  positions follow the parameters (x, y, z each); a corner within Snap
  distance of an existing point uses it. With Corners 0, the face goes
  through the group's points, ordered by angle around their centroid in
  their best-fit plane. It winds against any face sharing one of its edges
  (a refilled hole faces like its surroundings), else like the faces around
  its points. The new face is the output selection.
- **The primitives** (Create › Primitives; `primitives/` builds them in
  place on the pool, `verbs/create*.lucb` declares them): **Box** (size and
  divisions per axis; Bevel rounds every outer edge with PolyBevel at Bevel
  segments; one division each way is `Mesh.cube`, point for point),
  **Grid** (width, depth, columns, rows) and **Plane**, **Sphere** (UV:
  columns and rows), **Icosphere** (0–9 subdivisions: 10 × 4ⁿ + 2 points,
  20 × 4ⁿ faces), **Quad Sphere** (a divided cube on the sphere: 6d² quads),
  **Cylinder** and **Cone** (top radius 0 an apex, more a frustum; rows;
  caps None, N-gon, Fan or Grid in Cap rings bands), **Pipe** (a wall of a
  thickness, or one open wall), **Disc** (N-gon, Fan or Grid fill in
  rings), **Torus** (major and minor segments, Twist), **Capsule** (cap
  rows and body rows), **Platonic Solid** (the five, resting on a face) and
  **Helix** (a spring: radius, wire, turns, height, steps a turn, sides,
  caps). Each stands on its base at Position along Up, turned by Turn
  (`primitives/placement.lucb`); with Name piece on (Edit Mesh's steps) its
  faces take the path /box1, /box2, …. The new faces are the output
  selection. As a node a primitive has no input.
- **Shrinkwrap** (points; `inputs` 2, the reference required): the group's
  points onto the reference surface, Nearest, Along normals or Along
  vector (either way), Offset off it along its normal, Strength of the way;
  points whose line misses stay, with a warning. **Relax** given a
  reference keeps its points on it (each round ends with them pulled back).
  Both query the reference's spatial index (`TriangleIndex.nearest_point`,
  seeded with the neighboring point's distance) in parallel.
- **Poly Pen** (edges or points, native; positions after its parameters):
  one action of the Poly Pen tool, replayable: Extend a boundary edge into a
  triangle (one position) or a quad (two, each paired with the edge point
  it does not cross to), Fill corner at a point between exactly two
  boundary edges, Split an edge at a position. New faces wind against the
  face beside their edge. `Verbs.nearest_boundary_edge(mesh, point)` is the
  edge its Ctrl-click extends.
- **Circularize** (edges, faces, points as the edges between them): each
  loop of the group's edges a circle round its center (the points' mean
  weighted by their edges' lengths) in its plane (Newell's normal), each
  open run an arc of the circle that fits it (Kåsa's least squares in its
  plane); faces give their regions' outlines, and a region's inner points
  follow along their rays from the center when its outline is star-shaped
  about it, or between two concentric circles for a ring of faces (a
  hole's rim; the inner circle keeps its share of the outer's radius).
  Radius 0 fits; Even spaces the points at equal angles (the rotation that
  fits their own angles best), else each keeps its angle; Flatten, Twist,
  Influence. **Straighten** (edges, points): each run's inner points onto
  the line between its ends, at equal steps (Even) or their shares of its
  length; loops stay, with a warning. **Space Evenly** (edges, points):
  each run's or loop's points slid along it to equal lengths apart, on the
  polyline (Linear) or on the centripetal Catmull-Rom spline through them
  (Smooth), a run's ends and a loop's first point held; chains run in
  parallel. **Make Planar** (faces, everything with none): rounds of each
  group face's plane (its corners' mean and Newell's normal), then each
  point Factor of the way to the mean of its projections onto its group
  faces' planes, both passes in parallel (Blender's Make Planar Faces).
- **Recalculate Normals** (faces, everything with none): each island of the
  group (faces joined across edges of exactly two faces, both in it) wound
  one way by a breadth-first walk over each corner's link to its neighbor
  (found in parallel), then facing out by the signed volume it encloses
  about its center (summed in parallel pieces), or, too flat to tell, the
  winding most of its faces had; Inside turns every island in; faces that
  cannot agree (a Möbius strip) are reported. The faces turned are rebuilt
  reversed in parallel ranges and are the output selection.
- **Edge marks.** **Hard Edges** and **Soft Edges** (edges) set the edge
  attribute `sharp` to 1 or -1 (Mode Clear puts their own back to 0);
  **Smooth by Angle** (edges, faces, everything with none) sets every group
  edge hard where its faces meet at more than Angle, else soft (Keep hard
  edges keeps the hard ones), Maya's Set Normal Angle and Blender's Smooth
  by Angle. A mesh with `sharp` on its edges shades by them: the smooth
  normals (`ShadingCache`) split the faces round each point into fans at its
  hard edges, joined across its soft ones and across an unmarked edge whose
  faces meet within the 60° cusp; each corner takes its fan's angle-weighted
  normal. One hard edge at a point splits nothing there (its faces still
  join round the point), as Blender's sharp edges. A mesh changing `sharp`
  (`put_attribute`, `with_attribute_entry`, `without_attribute`,
  `renamed_attribute`, `remove_attribute`) takes a fresh shading cache.
  **Mark Seam** (edges) sets `seam` to 1 (Clear: 0); **Seams from Islands**
  (faces, everything with none) marks the group's edges whose two faces give
  either end point different corner UVs (`uv` on corners; per-point UVs make
  no islands, and no UVs are refused) and clears the rest, Mark hard
  marking them hard too. A mark counts where it is above 0 (`EdgeMark`), so
  a soft edge delimits no Connected; the marks ride through later verbs on
  the edges' provenance. **Bevel Weight** sets `bevel_weight`.
- **Select verbs** (native: the group stays on its own domain): the select
  rules of `selecting/` after the modeling verbs, one each. They change no
  geometry; the output selection is what the rule made, on its own domain.
  A rule is a `SelectRule` (name, label, group function, family, icon,
  levels, picks, rows, `whole`, kernel) in its family's file and a line in
  `selecting/registry.lucb`: Loop, Ring, Boundary Loop, Loop to Region,
  Grow and Shrink Selection, Border, Connected, Linked Flat, Shortest Path,
  Similar, Sharp Edges, By Sides, By Area, By Normal, Non-manifold, Loose,
  Interior Faces, Checker, Random, Mirror Selection, Convert. Edge loops
  follow Blender's walker rules (luced-3d docs/research/POLY-MODELING.md
  §5.2); Checker keeps runs of Selected elements and skips runs of
  Deselected ones, counted across each island of the group from its lowest
  element, shifted by Offset.

New corners inside a face blend that face's corners (the builder's mixed
corners), so UVs follow insets, slides and cuts; every other attribute and
group follows the parents. A verb with nothing to do, or a result with
degenerate faces, passes its input through with a warning. Edge output
selections are named by point pairs (`TopologyBuilder.select_edge`) and found
on the result.

`ComponentTransform.of(numbers, centroid)` reads Transform Components'
numbers (translate, rotate in degrees, scale, pivot mode, custom pivot) as a
rotation-and-scale, a translation and a pivot, and `matrix(translation)`
composes the move: for editors that move whole things rather than points
(Edit SDF's primitives, Edit Sketch's curves, luce-cad's models).

Faces a builder copies keep their triangles (CAD cut cells survive); runs of
untouched faces copy in one pass (`copy_faces`), and only new faces are ear
clipped. `tests/bench/run.py --base <luce-base>` times every verb on the 837×837
grid (one `--native --opt 3` run each, connectivity caches warm, output mesh
and attributes included; the primitives run on nothing, and Shrinkwrap and
Relax read the grid in triangles, turned a little and lifted 0.3, as their
reference):

| Verb run | Time | Faces out | Warning |
|---|---:|---:|---|
| Transform Components, 1k faces | 15.4 ms | 700,569 |  |
| Smooth, everything | 5.3 ms | 700,569 |  |
| Delete, 1k faces | 5.9 ms | 699,569 |  |
| Reverse, 1k faces | 13.5 ms | 700,569 |  |
| Triangulate, half | 35.5 ms | 1,050,570 |  |
| Duplicate, 1k faces | 11.5 ms | 701,569 |  |
| Subdivide, everything to 2.8M faces | 598.6 ms | 2,802,276 |  |
| Fuse, 1k faces' points | 26.6 ms | 700,569 |  |
| PolyExtrude, 1k faces as a region | 23.9 ms | 702,247 |  |
| PolyExtrude, 1k faces one by one, inset, 2 divisions | 27.1 ms | 708,569 |  |
| PolyExtrude, 100k faces as a region | 71.2 ms | 702,483 |  |
| PolyExtrude, 3 edges | 47.0 ms | 700,572 |  |
| Inset, 1k faces as a region | 26.1 ms | 702,247 |  |
| Inset, 100k faces as a region | 80.1 ms | 702,483 |  |
| PolyBevel, 1k faces' inner edges | 83.5 ms | 705,240 |  |
| PolyBevel, 100k faces' inner edges, 3 segments | 325.0 ms | 2,197,462 |  |
| PolyBevel, every edge (1.4M) | 516.7 ms | 2,798,929 |  |
| Loop Cut, one ring of 837 quads | 42.9 ms | 701,406 |  |
| Loop Cut, every ring both ways | 385.9 ms | 1,401,138 |  |
| Bridge, two facing 837-edge loops, 3 cuts | 19.9 ms | 703,080 |  |
| Merge Points, a face's points at their center | 23.9 ms | 700,568 |  |
| Merge Points, 250 pairs as islands | 24.3 ms | 700,569 |  |
| Dissolve, 250 edges between face pairs | 37.9 ms | 700,278 |  |
| Dissolve, 250 points | 33.8 ms | 699,821 |  |
| Fill, a 22-edge hole | 45.4 ms | 700,561 |  |
| Fill, a 22-edge hole as a fan | 19.5 ms | 703,929 |  |
| Split, 1k faces | 14.4 ms | 700,569 |  |
| PolyDraw, a quad drawn onto the grid, its corners snapped | 26.0 ms | 700,570 |  |
| PolyDraw, through 4 selected points | 13.0 ms | 700,570 |  |
| Clean, everything | 25.5 ms | 700,569 |  |
| Poke, 1k faces | 17.3 ms | 703,569 |  |
| Poke, 100k faces | 53.7 ms | 1,000,569 |  |
| Rotate Edge, a 1k faces' edges | 46.2 ms | 700,569 | Edges on a boundary, sharing a face with another, or whose new diagonal exists already were left |
| Solidify, 100k faces | 33.6 ms | 802,483 |  |
| Solidify, everything, even thickness | 69.7 ms | 1,404,486 |  |
| Symmetrize, everything | 103.1 ms | 701,406 |  |
| Snap to Symmetry, every point | 43.6 ms | 700,569 |  |
| Grid Fill, a 22-edge hole | 17.4 ms | 700,569 |  |
| Bridge, two 837-edge loops, 3 cuts, blend path and profile | 19.3 ms | 703,080 |  |
| Bridge, the second loop as a second pick | 27.5 ms | 700,569 |  |
| Edge Split, a 1k faces' inner edges | 58.1 ms | 700,569 |  |
| Rip, a run of 10 edges, filled | 55.9 ms | 700,581 |  |
| Separate, 1k faces | 23.0 ms | 700,569 |  |
| Separate, 100k faces as loose parts | 25.5 ms | 700,569 |  |
| Delete Edge Loop, a 1k faces' inner edges | 45.4 ms | 699,570 |  |
| Limited Dissolve, everything (one face) | 149.5 ms | 1 |  |
| Collapse, a 1k faces' block | 24.8 ms | 699,567 |  |
| Merge Points, a face's points at a point | 20.1 ms | 700,568 |  |
| Target Weld, a point onto its neighbor | 17.5 ms | 700,569 |  |
| Knife, a stroke across 837 faces, through | 54.7 ms | 701,406 |  |
| Spin, a run of 10 edges about an X axis, 12 steps | 17.0 ms | 700,689 |  |
| Screw, a run of 10 edges about an X axis, 2 turns of 12 | 17.7 ms | 700,809 |  |
| Subdivide, everything, linear, smoothness 1 | 724.5 ms | 2,802,276 |  |
| Smooth, everything, keep volume and boundary | 13.0 ms | 700,569 |  |
| Relax, everything, 5 rounds | 29.2 ms | 700,569 |  |
| Triangulate, everything, beauty | 70.9 ms | 1,401,138 |  |
| Tris to Quads, the grid in triangles | 136.6 ms | 700,569 |  |
| Decimate, 100k triangles collapsed to half | 88.1 ms | 1,351,137 |  |
| Decimate, un-subdivide 836×836 quads | 76.0 ms | 174,724 |  |
| Collapse, every edge of 100k faces | 23.5 ms | 600,568 |  |
| Grid, 1024 × 1024 (1M faces) | 23.2 ms | 1,048,576 |  |
| Box, 409 divisions each way (1M faces) | 21.7 ms | 1,003,686 |  |
| Box, 32 divisions, every edge rounded at 4 segments | 2.8 ms | 7,776 |  |
| Sphere, 1448 × 724 (1M faces) | 23.5 ms | 1,048,352 |  |
| Icosphere, 8 subdivisions (1.3M faces) | 21.3 ms | 1,310,720 |  |
| Quad Sphere, 409 divisions (1M faces) | 23.3 ms | 1,003,686 |  |
| Cylinder, 1024 sides × 1024 rows, grid caps (1.2M faces) | 27.9 ms | 1,179,648 |  |
| Torus, 1024 × 1024 (1M faces) | 22.0 ms | 1,048,576 |  |
| Capsule, 1024 sides, 256 cap rows, 512 rows (1M faces) | 23.6 ms | 1,048,576 |  |
| Helix, 40 turns of 512 steps, 48 sides (1M faces) | 20.6 ms | 983,042 |  |
| Shrinkwrap, every point (702k) onto a scan just above (1.4M triangles) | 62.8 ms | 700,569 |  |
| Shrinkwrap, every point along a vector onto that scan | 36.6 ms | 700,569 | Some points' lines miss the reference surface; they stay where they were |
| Relax, every point, 5 rounds kept on that scan | 247.0 ms | 700,569 |  |
| Poly Pen, a boundary edge extended | 14.5 ms | 700,570 |  |

The Stage 7 tools on about a million faces (the 1024 × 1024 grid, its rows
of edges a named group; the grid roughened by Mountain for Straighten, Space
Evenly and Make Planar; a 1448 × 724 sphere with its first 524,288 faces
reversed; the grid with projected UVs), and the shading normals of that
sphere by the cusp and by its edge marks after Smooth by Angle:

| Verb run | Time | Faces out | Warning |
|---|---:|---:|---|
| Circularize, the whole 1024² grid (its outline a circle, 1M inner points mapped) | 89.7 ms | 1,048,576 |  |
| Circularize, a 512² block in the grid (262k faces) | 34.8 ms | 1,048,576 |  |
| Circularize, every row of the grid as an arc (1025 runs, 1M edges) | 80.1 ms | 1,048,576 |  |
| Straighten, every row of the rough grid (1025 runs, 1M edges) | 39.9 ms | 1,048,576 |  |
| Space Evenly, every row, linear | 56.9 ms | 1,048,576 |  |
| Space Evenly, every row, smooth | 124.7 ms | 1,048,576 |  |
| Make Planar, every face of the rough grid, 10 rounds | 43.1 ms | 1,048,576 |  |
| Recalculate Normals, the sphere with half its faces turned in | 51.4 ms | 1,048,352 |  |
| Recalculate Normals, the grid (nothing turns) | 27.8 ms | 1,048,576 |  |
| Hard Edges, every edge of the grid (2.1M) | 3.0 ms | 1,048,576 |  |
| Soft Edges, every row | 2.7 ms | 1,048,576 |  |
| Smooth by Angle, the whole sphere | 18.1 ms | 1,048,352 |  |
| Mark Seam, every row | 2.8 ms | 1,048,576 |  |
| Seams from Islands, the grid with UVs | 19.9 ms | 1,048,576 |  |
| Bevel Weight, every row | 1.7 ms | 1,048,576 |  |
| Shading normals, the 1M-face sphere, by the cusp | 27.4 ms | 1,048,352 |  |
| Shading normals, the 1M-face sphere, by its edge marks (every edge marked) | 22.9 ms | 1,048,352 |  |
