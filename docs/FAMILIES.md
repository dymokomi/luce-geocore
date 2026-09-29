# Geometry families beyond meshes

A `GeometrySet` holds one component per family. Meshes, points and instances
are described in [API.md](API.md). This file covers curves and the set verbs.

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

Missing Bezier handles are automatic: one sixth of the neighbours'
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

## Benchmarks

`tests/bench/run.py --base <luce-base>` also runs `tests/bench/geometry.lucb`
(one `--native --opt 3` run each, Apple M-series):

| Case | Time | Elements out |
|---|---:|---:|
| Curves: build 10k Bezier curves of 32 points | 24.6 ms | 320,000 |
| Curves: evaluate 10k Bezier curves, resolution 12 | 10.9 ms | 3,730,000 |
| Curves: tangents, normals and lengths of those | 61.6 ms | 3,730,000 |
| Curves: evaluate 10k NURBS curves (order 4), resolution 12 | 23.1 ms | 3,490,000 |
| Resample Curve: 10k curves to 64 points | 165.2 ms | 640,000 |
| Curve to Mesh: 1k Catmull-Rom curves, 12-point circle | 82.1 ms | 4,466,000 |
| Mesh to Curve: the 837×837 grid's boundary | 51.9 ms | 3,348 |
| Mesh to Curve: every edge of the 837×837 grid | 345.9 ms | 1,402,808 |
