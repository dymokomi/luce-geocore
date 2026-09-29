# Validation

`./test.sh` builds `tests/main.lucb` at native optimization levels 0–3 and in
both C modes. Every mesh check also runs with allocation failure injected at each
stage, and must leave no allocation live.

- Curved-polygon display triangulations: exact index retention through detached
  copies, attributes, affine/reflected placement, merging, deletion/compaction
  and face reversal; arbitrary deformation invalidation; builder rollback;
  rejection of out-of-face, partial, reversed and repeated triangles. Allocation
  failure injection exercises 256 construction/copy/operation stages and checks
  that no package allocations remain live.
- Edge dissolve preserves the exact source display surface across planar,
  nonplanar and thin-cell unions at two scales (eight combinations). A pinched
  union is rejected instead of publishing a repeated boundary vertex.
- Local dissolve staging is compared after every accepted/rejected operation
  against sequential immutable dissolves on planar/nonplanar grids in both
  windings. Points, face/corner order, normals, display indices and numeric
  attributes across all four domains match exactly. Neighbor slots remain
  reciprocal. Zero edit budgets, nonmanifold edges and inconsistent winding
  reject without mutation. 192 injected allocation cutoffs check cleanup;
  a separately denied display-validation allocation leaves the edit retryable.
- Polygon face normals use an extent-relative area threshold, consistent with
  polygon triangulation, rather than the generic vector normalization cutoff.
  Scale regressions cover 96 concave-polygon combinations of size, translation,
  plane and winding through both direct construction and the mesh builder;
  they verify analytic area, unit normals and directed display triangles.
  A tiny non-collinear UV wedge is accepted and a collinear face is rejected.
  This is a polygon-construction contract, not a claim that every CAD operation
  is independent of units or tolerances.
- Stranded-ear recovery has 378 scale/pose/winding/start/perturbation cases.
  Every supplied boundary interval survives once, every interior diagonal twice
  with opposite use, and positions, corner order, signed area and positive
  conditioned triangles are checked. Another 96 injected-allocation stages
  exercise cleanup of the exceptional partition tables. Disabling the fallback
  in an isolated negative-control build makes this regression fail.
- Lazy spatial-index checks cover failure/retry at ten allocation cutoffs,
  including BVH growth, and warmed queries with all further allocation refused.
  Attribute snapshots keep the same completed cache after the original closes.
  Eight rounds of eight simultaneous native readers exercise first publication
  on a detached mesh, then 100 repeated query sets per reader; all allocations
  are accounted for after join/close. Two nonplanar quad triangulations verify
  that queries still use the exact retained display surface, not a new diagonal.
- Point/triangle distance avoids the nearly equal products in the Gram
  determinant. It uses signed cross-product areas, a better-conditioned origin,
  and boundary candidates. 4,334 primitive queries cover thin triangles,
  vertex permutations, scales, translations, axis planes, known interior/edge/
  exterior projections, nonzero normal distances, and degenerate vertices.
- Verbs: golden checks of every verb on a 4 by 4 grid carrying uvs, groups
  and ids (`verb_checks`: counts, output selections, propagation,
  determinism, the Edit engine's symmetry, soft falloff, soft weights and
  kept selections); the G6 verbs' element counts and closed surfaces
  (`g6_checks`); PolyDraw (`polydraw_checks`); subdivision and creases
  (`subdivision_checks`).
- Groups: every row of Houdini's group-syntax table
  (`group_language_checks`), selections and their encoder round trips.
