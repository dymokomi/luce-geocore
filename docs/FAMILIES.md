# Geometry families beyond meshes

A `GeometrySet` holds one component per family. Meshes, points and instances
are described in [API.md](API.md). This file covers curves, volumes and
SDFs, the set verbs, and the geometry codec.

## Curves

`Curves` (`luce_geocore.curves`) stores many curves in one structure of
arrays, after Blender's `CurvesGeometry`:

- control points are f32 positions over an f64 origin, as a mesh's points are;
- `offsets` splits the points into curves;
- attributes live in the same `AttributeStore` as a mesh's.

The domains follow Houdini: the control points are the `point` domain, and
each curve is a primitive, the `face` domain. Group expressions, the Group
Type menu's "Primitives" and attribute tests therefore address curves
unchanged.

How a curve evaluates is held in builtin attributes. An absent attribute takes
its default:

| Domain | Name | Type | Meaning (default) |
|---|---|---|---|
| face | `curve_type` | int8 | 0 poly, 1 Bezier, 2 NURBS, 3 Catmull-Rom (0) |
| face | `cyclic` | boolean | closed (false) |
| face | `resolution` | int32 | evaluated points per segment or knot span (12) |
| face | `order` | int8 | NURBS order, 2..8, at most the point count (4) |
| face | `knot_mode` | int8 | 0 uniform, 1 endpoint (clamped), 2 custom (1) |
| point | `w` | float32 | NURBS weight (1) |
| point | `handle_l`, `handle_r` | float32×3 | Bezier handles in the positions' frame (absent: automatic) |

Custom knots are one f32 column for every curve, split by `knot_offsets`.

Missing Bezier handles are automatic: one sixth of the neighbors'
difference, with open ends mirrored. A Bezier curve without handles
therefore draws the same curve as a Catmull-Rom curve through the same
points.

NURBS basis functions follow The NURBS Book (A2.2). Knots follow Blender's
normal and endpoint modes.

### Evaluation

The evaluated curves are a lazy cache (`evaluate.lucb`, `frames.lucb`), built
by whichever thread asks first, in parallel over curves:

- evaluated offsets and the NURBS basis, keyed by the ids of the offsets,
  types, closure, resolution, order, knot modes and knots;
- evaluated positions, keyed also by the positions, handles and weights;
- tangents, minimum-twist normals (Blender's) and arc lengths, following the
  positions.

Shares of a curves value share its cache. A value made by moving points
(`placed`, Set Curve Type) starts with its source's evaluation shape, so the
basis is not rebuilt.

`CurvesBuilder` builds curves point by point. Each point names its parents in
a source: one, or two with a mix. `finish` carries every attribute and group
through the parents:

- floats interpolate;
- integers and text take the nearer parent;
- a group keeps a point only when both parents are members.

### Curves in a set

The `curves` component type covers:

- sharing;
- bounds of the evaluated points;
- placement, which turns positions, handles, vectors and normals;
- joining, where a side lacking weights or handles gets its defaults;
- path filters on the curve text attribute `path`;
- descriptions ("3 curves / 8 curve points").

`curves_subset` and `curves_reordered` pick, reorder and reverse curves, and
carry every attribute. A reversed curve swaps its handles' sides and mirrors
its custom knots.

### Groups on curves

`curve_group_bits` runs the same group programs over curve points and curves:

- numbers, names and name filters;
- `@P`, `@ptnum`, `@primnum`, `@elemnum` and attribute tests;
- `grow` and `shrink` along curves;
- `border`, the ends of each run of members;
- `connected`, which takes whole curves.

A point group converts to curves whose every point is a member. A curve group
converts to all the curve's points. Edge forms, `loop` and `ring` fail on
curves.

### Edit Sketch

`Sketches` (curves/sketch.lucb, sketch_pick.lucb) edits planar sketches as
curves for luced-3d's Edit Sketch.

- The sketch plane is the set's detail attributes `sketch.plane_origin`
  (role position) and `sketch.plane_normal` (role normal), so it exists before
  any curve, moves with a Transform and reaches later nodes. Unset, it is the
  ground (ZX). Its in-plane axes are X, Y on XY; Y, Z on YZ; Z, X on the
  ground.
- Shapes on the plane: line, polyline, arc and circle (exact NURBS),
  rectangle (closed poly), spline (cubic NURBS).
- Picking uses faceless point clouds: the control points (Points), or
  samples along each curve tagged `curve` and `segment` (Object,
  Segments). Segments run between consecutive control points and are
  numbered across curves.
- Steps name points, segments or curves by a group on that cloud (Group Type
  points, edges or primitives): moves keep their translation in the plane
  and snap as they happen when the numbers after Transform Components'
  fifteen give a grid spacing or an end reach;
  grid snaps, end snaps (onto the nearest other end), deletes (a segment
  splits an open curve and opens a closed one), close and open.
- Every position change goes through `placed_curves(curves, targets, moved,
  linear)`, the one place a constraint solver would adjust the targets.

## Detail attributes

A set holds its own attributes on the detail domain, one element each, apart
from its components, as Houdini's detail attributes are. They exist with no
components at all.

- `with_detail(name, values, role)`, `detail_value`, `detail_width`,
  `has_detail`, `without_detail`, `detail_count` and `detail_name` from Luce;
  `set_detail` and `set_put_detail` from Base.
- Copies share their columns. Placing a set moves width-3 float attributes
  by role: positions take the whole matrix, vectors its linear part, normals
  the inverse transpose.
- Joining keeps the first set's values and adds the second's it lacks.
- The codec writes them as attribute children of the geometry element.

## Volumes and SDFs

### Volumes

A volume (`luce_geocore.fields`) holds named `SparseGrid`s, each shared by
count. The layout is NanoVDB-like (design D9), flat and read-only:

- 8×8×8 leaves, whose keys are sorted Morton codes of leaf coordinates;
- 512 f32 values per leaf, x fastest;
- 8 active-mask words per leaf;
- an index-to-world affine transform;
- a background value for everything outside the leaves.

Builders fill leaves in parallel and publish a new grid; nothing writes a
published one. Placing a volume composes its grids' transforms.

The two grid classes:

- **level set**: signed distances in a narrow band, negative inside;
- **fog**: densities.

### SDFs

An SDF is an analytic program: a postfix column of ops with 16 parameters
each.

- Primitives: sphere, rounded box, torus, capsule, cylinder.
- Booleans: union, subtract, intersect, each hard or smooth (polynomial
  smooth min).
- A transform pair: points map in, distances scale back.
- `round` and `shell`.

Programs compose by concatenation. Placing an SDF wraps its program in a
transform, and joining two SDFs makes their union. Every op keeps the field
1-Lipschitz.

`SdfEdits` (fields/sdf_tree.lucb, sdf_proxy.lucb, sdf_edit.lucb) edits a
program primitive by primitive for luced-3d's Edit SDF.

- `SdfTree` parses the postfix program once into nodes. A primitive's number
  is its place among the primitives. Its placement is the transform directly
  around it (through modifiers); its boolean is the one taking it as the
  second operand.
- `SdfRewrite` makes every edit one linear pass over the ops. Moves read
  Transform Components' numbers through `ComponentTransform` (verbs), which
  Edit Sketch and luce-cad's model moves share. A move composes
  into the placing transform, or wraps the primitive in a new one; the world
  delta is conjugated into the frame the placement lives in. A boolean change
  rewrites one op. A delete drops the primitive with what wraps it and each
  boolean left with one operand.
- Proxies: each primitive's own shape (sphere, box, torus, capsule,
  cylinder), placed by every transform around it, tagged `sdf_prim`. Their
  topology depends only on the shapes, so moves keep selections, and a
  subtracted primitive stays pickable.

### Conversions

- **SDF to level set** (`sampled_sdf`):
  - First, blocks of 8×8×8 leaves are skipped when their center is farther
    from the surface than their half diagonal plus the band. Then the same
    test runs per leaf.
  - The leaves left are sampled in parallel.
- **Mesh to level set** (`mesh_level_set`, `mesh_distance.lucb`):
  - Distances are rasterized per leaf. Each triangle is binned into the leaves
    its band-grown box touches.
  - A leaf walks its triangles over each grown box's voxels, keeping the
    nearest point and its feature (vertex, edge or face). A cheap box test
    against the best distance so far comes first.
  - The sign is the side of that feature's angle-weighted pseudo-normal
    (Bærentzen and Aanæs). It is exact for closed, consistently oriented
    meshes, concave edges and saddle vertices included; an L-shaped prism in
    `tests/field_checks.lucb` checks every band voxel.
  - Voxels beyond the band take a neighbor's side. A region no band voxel
    reaches asks the BVH once.
  - A mesh with more triangles than band voxels (a dense, finely tessellated
    one) is answered by a BVH query per voxel instead. Leaves and 4×4×4
    blocks beyond the band take one query at their center. A voxel beside
    one that is a voxel beyond the band needs no query, since the distance
    changes by at most a voxel.
- **Points to level set** (`points_level_set`): a union of spheres. Each
  point writes only the voxels within its reach.
- **Surface nets** (`surface_mesh`):
  - Three parallel passes over leaves, each reading a 9×9×9 neighborhood
    block: crossing cells, then quads, then filling.
  - Cells touching a level set's missing leaves make no surface. Those
    leaves have no known side, and the band keeps every cell the real
    surface crosses whole.
  - An SDF can pull the vertices onto its exact surface with two Newton
    steps.
- **Slices** (`slice_mesh`): a plane of quads across a field. Each point
  carries `value` and a color `Cd`:
  - distances: blue inside, orange outside, with contour bands;
  - densities: gray.

### Previews and files

The viewport draws an SDF or a level set by its surface preview:

- an SDF's zero set at 1/128 of its extent, made exact;
- a level set's zero set.

A fog volume has no surface preview: viewports ray-march its densities
(luce-3d's `FogVolume`). How it looks is Houdini's Volume Visualization:
the **Volume Visualization** verb puts volvis_* detail attributes on the set
(`volvis_densityscale`, `volvis_smokecolor`, `volvis_shadowscale`,
`volvis_emitscale`, `volvis_emitcolor`, `volvis_emitfield`,
`volvis_stepsize`) and leaves the grids shared and untouched; `volume_look`
reads them back over the defaults. The emission field names a grid whose
values emit light; it is not drawn as smoke itself.

The preview is built once and kept with the component. A drag's frames may
ask for a quick SDF preview instead (1/40 of the extent), kept apart, so the
full one is built after the release. The codec writes:

- grids with their keys, values and masks as columns;
- SDF programs as `ops` and `params`.

## Gaussian splats

A splat cloud is the points family with conventional point attributes, as in
Houdini: `orient` (x, y, z, w), `scale` (linear σ), `opacity` (linear), `Cd`
(linear), one ragged vec3 `sh` array (SH bands 1..d, coefficient-major, RGB per
item: 0, 3, 8 or 15 items), an optional `restorient`, and the detail
`gsplat_color_space` (`srgb` or `linear`). `src/splats/conventions.lucb` states
them, and the design is luced-3d's `docs/research/GAUSSIAN-SPLATS.md`.

- **Color.** Bake decodes only the DC color into a linear `Cd`. The SH bands are
  offsets in the file's encoding and stay as they are, so a splat's color toward
  a direction is decode(encode(`Cd`) + bands): exactly the trained color
  (`display_color`). Export encodes `Cd` back (`file_dc`).
- **Math** (`luce_geocore.splats`): sigmoid and logit; the 3DGS SH basis and
  evaluation (degrees 0..3); `ShRotation`, each band's real Wigner D-matrix solved
  from the basis at sample directions, with mirrors as a rotation plus the point
  inversion; a Jacobi symmetric 3×3 eigensolver; covariance compose and
  decompose; the polar rotation of a linear map.
- **Placement.** A Transform moves cloud attributes by role (position, vector,
  normal, and the new `Role.rotation`, which `orient` has; meshes, curves and
  details turn rotations too). A splat cloud's covariances become L Σ Lᵀ: a
  similarity turns `orient` and scales `scale`, anything else is decomposed.
  The SH are never rotated: `restorient` keeps the SH frame,
  orient · restorient⁻¹, and is written (as `orient`) the first time a
  transform turns it. A mirror negates the odd SH bands.
- **Merge** pads the lower SH degree with zero bands and adds `orient` and
  `restorient` where one side lacks them.
- **Nodes** (category GSplats): **Bake GSplats** reads the 3DGS PLY's raw names
  (`f_dc_*`, `opacity` logits, `scale_*` logs, `rot_*` w, x, y, z, with `f_rest`
  as `f_rest_*`, a channel-major array or luce-ply's coefficient-major vec3
  array), Houdini's (`GS_Alpha`, `GS_SPH_R/G/B`), or plain points (round splats
  from `pscale`). **GSplats SH Degree** truncates or pads the bands.
- **Export.** `unbaked_set` (`GeometrySet.unbaked_splats` in Luce) gives the raw
  names back, `restorient` baked into `f_rest`. Bake keeps `scale`, `opacity`
  and `Cd` in f64 and the file's quaternion as it is, so a file's values come
  back bit for bit (`tests/splats`).
- **Renderers** find a set's splats with `set_splats` (Base) or
  `GeometrySet.splat_count` (Luce), and any cloud, splats or plain points,
  with `set_cloud`; `cloud_positions_id` is its positions' change id, which a
  GPU copy keys on (luce-3d's GaussianSplats).

## Set verbs and the verb catalog

A set verb (`luce_geocore.set_verbs`) takes whole geometry sets. Mesh verbs
take the realized mesh. A set verb is described with the same `ParmSpec` rows
and has the same Group and Group Type, plus:

- its input count: 0 for a generator, 2 when it reads a second set;
- whether the second input must be connected.

`GeometryVerbs.run(name, set, second, group, group_type, numbers)` runs one,
and `SetVerbResult` holds the output set and a warning.

`VerbCatalog` lists every verb a node can run: the mesh verbs first, then the
set verbs. luced-3d generates its whole node catalog from it.

The curve verbs:

- **Curve Line**, **Curve Circle**, **Curve Arc** and **Curve Spiral** are
  generators, in any curve type. A NURBS circle or arc is exact: rational
  quadratic arcs with custom knots. A Bezier circle uses 4/3 tan(a/4)
  handles.
- **Resample Curve**: evenly spaced points by count or by length, as poly
  curves.
- **Trim Curve**: keeps the part of each curve between two factors or lengths.
- **Fillet Curve**: rounds control-polygon corners with arcs, limited to half
  the shorter edge.
- **Reverse Curve**: runs the curves the other way.
- **Set Curve Type**: changes how the curves evaluate.
- **Curve to Mesh**: sweeps a circle, or the second input's first curve (its
  XY plane), along the curves.
  - The rings sit on minimum-twist frames.
  - Caps are optional.
  - Faces take their curve's attributes and ring points their control
    points'.
  - The mesh gets a corner `uv`.
- **Mesh to Curve**: chains of the group's mesh edges, or of their boundary,
  become poly curves. Pass-through points join chains, and closed chains
  become cyclic.

The volume verbs:

- **SDF Sphere**, **SDF Box**, **SDF Torus**, **SDF Capsule** and **SDF
  Cylinder** are generators.
- **SDF Boolean**: union, subtract or intersect of two SDFs, with a smoothness.
- **SDF Modify**: round outward, or hollow into a shell.
- **SDF to Volume**, **Mesh to SDF** and **Volume from Points** make level
  sets, with a voxel size and a band.
- **Convert to Mesh**: surface nets of the SDF and every grid, SDF surfaces
  made exact.
- **Volume Slice**: a colored plane, beside the field or alone.
- **Volume**: a fog or level-set grid over a box, named by the node's Name row
  (`VerbCatalog.text_row`, sent as the run's group text), with a voxel size,
  background and initial value, dense or empty. It joins the input's volume,
  replacing a grid of its name: the start for a Code node running over voxels.

## Geometry files (.prism)

`GeometryFile.save(geometry, path, key)` writes a whole set as a prism v4
binary crate (PRSMC, luce-prism's format), and `GeometryFile.load(path)` reads
it back. `GeometryFile.key(path)` reads only the key recorded at the root.
Everything is written:

- every component, every attribute and group, every flag;
- nested instance sets.

The round trip is exact: floats are written bit for bit.

The document is a tree of elements:

```
/geometry              geometry    int64 version, int64 key
  /geometry/a0         attribute   the set's detail attributes (as below)
  /geometry/mesh       mesh        float64[3] origin, float32[n,3] P, int32 face_offsets,
                                   int32 corner_points, int32 triangles, [float64[n,3] precise]
    /geometry/mesh/a0  attribute   str name, domain, type; int64 width, single, flags, role,
                                   elements; [uint8 table]; typed value
  /geometry/points     points      origin, P
  /geometry/curves     curves      origin, P, offsets, [knots, knot_offsets]
  /geometry/instances  instances   int64 count, prototypes; int32 prototype;
                                   float64[n*9] placement; uint8 visible
    .../a0             attribute   (a row attribute, as above; point domain)
    .../p0             geometry    (a prototype set, written once)
  /geometry/volume     volume      int64 count
    .../g0             grid        str name; int64 class; float64 background, transform[12];
                                   uint64 keys; float32[n,512] values; uint64[n,8] masks
  /geometry/sdf        sdf         uint8 ops; float32[n,16] params
```

Derived caches are never written: normals, edges, evaluated curves, BVHs.

The writer (`io/crate.lucb`) streams:

- It collects the element tree and the string table first.
- Each column's payload then goes straight from its block to the file,
  through a temporary file that is renamed over the destination.
- The reader reads each payload straight into the new column that will hold
  it.

Neither copies the data. luce-prism's in-memory document engine caps a file
at 256 MiB, so a column above 256 MiB is written as several properties:
`<name>_chunks` holds the count and rows, then `<name>_0`, `<name>_1`, and so
on. Files under 256 MiB open in luce-prism as ordinary documents; luced-3d's
tests check this.

Each family has a codec. Mesh, points, curves, instances, volumes and SDFs
are built in.
Another package registers its own once, before saving or loading:

```luce
from luce_geocore.kernel import register_codec, GeometryWriter, GeometryReader

register_codec(my_component_type(), encode, decode)
## encode(data: const void*, writer: GeometryWriter*, path: str) -> !
##   writer.crate.element(path, "<family name>"), then properties:
##   writer.crate.integer/number/triple/text/copied_array, a column with
##   writer.column / column_of / column_borrowed (see below; chunked as
##   needed), and writer.attributes(path, store) for an AttributeStore.
## decode(reader: GeometryReader*, path: str) -> void*!
##   reader.next_property() until none, reading each with integer/triple/
##   text/column[T](header); then reader.attributes(path, &store) and
##   reader.next_child(path) for child elements; returns the component data.
```

The element kind of a component is its family name. The loader finds the
codec by that name, and fails clearly when a family has none.

**Payload lifetimes.** The crate streams payloads when `save` runs, so every
payload must still be valid then.

- `writer.column(name, dtype, rows, columns, bytes)` copies the bytes. It is
  safe for temporaries, stack arrays and anything freed before the save.
- `writer.column_of(..., column: const Column[u8]*)` retains the column until
  the writer closes, with no copy.
- `writer.column_borrowed(...)` and `writer.crate.array_borrowed(...)` borrow.
  The caller keeps the bytes alive and unchanged until `save` returns. The
  built-in codecs use them for the columns of the set being saved, which the
  caller holds for the whole save.

`tests/codec_checks.lucb` writes a column from a temporary freed before the
save and reads the values back.

## Benchmarks

`tests/bench/run.py --base <luce-base>` also runs `tests/bench/geometry.lucb`
(one `--native --opt 3` run each, Apple M-series):

| Case | Time | Elements out |
|---|---:|---:|
| Curves: build 10k Bezier curves of 32 points | 24.6 ms | 320,000 |
| Curves: evaluate 10k Bezier curves, resolution 12 | 10.9 ms | 3,730,000 |
| Curves: tangents, normals and lengths of those | 61.6 ms | 3,730,000 |
| Curves: evaluate 10k NURBS curves (order 4), resolution 12 | 23.1 ms | 3,490,000 |
| Resample Curve: 10k curves to 64 points | 10.9 ms (165.2 ms serial) | 640,000 |
| Curve to Mesh: 1k Catmull-Rom curves, 12-point circle | 82.1 ms | 4,466,000 |
| Mesh to Curve: the 837×837 grid's boundary | 51.9 ms | 3,348 |
| Mesh to Curve: every edge of the 837×837 grid | 345.9 ms | 1,402,808 |
| Save: the 837×837 grid with uv to .prism (bytes) | 8.0 ms | 84,089,051 |
| Load: that .prism back (faces) | 19.3 ms | 700,569 |
| SDF to Volume: a smooth union, voxel 1/400 of its size (active voxels) | 57.1 ms | 3,706,635 |
| Surface nets: that level set (faces) | 107.7 ms | 848,874 |
| Surface nets projected onto the SDF (faces) | 165.4 ms | 848,874 |
| Mesh to SDF: a 64-segment sphere, voxel 0.01 (active voxels) | 57.4 ms (750.3 ms per-voxel BVH) | 751,940 |
| Mesh to SDF: the 837×837 grid, 256 voxels across (active voxels) | 369.1 ms (511 ms before) | 340,573 |
| Volume from Points: 100k points, radius 0.02, voxel 0.01 (active voxels) | 105.2 ms | 3,044,352 |
| Triangulate: a regular 20,000-gon (triangles) | 1.4 ms | 19,998 |
| Mesh: one 20,000-corner face, validated and triangulated (triangles) | 8.5 ms | 19,998 |
| Triangulate: a 5,003-corner comb of thin teeth (triangles) | 22.7 ms | 5,001 |
| Triangulate: a 5,000-corner spiral corridor (triangles) | 3.1 ms | 4,998 |

luced-3d's headless benchmark (`tests/bench/run.py`, `--native --opt 2`)
saves and loads cooked results:

| Case | Save | Load | File |
|---|---:|---:|---:|
| 700k-face grid (OBJ) | 3.8 ms | 17.0 ms | 39 MB |
| camera.step, tessellated (707k points, 655k faces, 9 attributes) | 11.8 ms | 25.5 ms | 122 MB |

Mesh to SDF at 256 voxels across the bounds (luced-3d headless benchmark):

| Case | Now (pseudo-normal signs) | Before (per-voxel BVH, face-normal signs) |
|---|---:|---:|
| 700k-face grid (an open plane of tiny quads; BVH path) | 461 ms | 691 ms |
| camera.step, tessellated (rasterized) | 2,798 ms | 41,636 ms |
| 64-segment sphere, voxel 0.01 (rasterized, geocore bench) | 57 ms | 750 ms |
