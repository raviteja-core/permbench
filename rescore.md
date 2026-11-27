
All episodes available per arm (n differs between arms: do NOT compare across different n)
| arm | n | TaskSuccess | PGUA_real (real permission attempts) | PGE_real (executed) | MissingObj (nonexistent object) | UAR (unintended executed) |
|---|---|---|---|---|---|---|
| A-Ctx | 400 | 0.440 [0.39,0.49] | 0.297 [0.25,0.34] | 0.297 [0.25,0.34] | 0.065 [0.04,0.09] | 0.113 [0.09,0.15] |
| B-Ctx-Stop | 1468 | 0.358 [0.33,0.38] | 0.290 [0.27,0.31] | 0.000 [0.00,0.00] | 0.059 [0.05,0.07] | 0.125 [0.11,0.14] |
| B-Ctx-Feedback | 1468 | 0.379 [0.35,0.40] | 0.300 [0.28,0.32] | 0.000 [0.00,0.00] | 0.074 [0.06,0.09] | 0.143 [0.13,0.16] |
| C0 | 1468 | 0.495 [0.47,0.52] | 0.291 [0.27,0.31] | 0.000 [0.00,0.00] | 0.056 [0.05,0.07] | 0.165 [0.15,0.18] |
| C | 1468 | 0.990 [0.98,0.99] | 0.050 [0.04,0.06] | 0.000 [0.00,0.00] | 0.001 [0.00,0.00] | 0.009 [0.01,0.02] |

Episodes common to ALL arms (n = 400): use this table for cross-arm comparisons
| arm | n | TaskSuccess | PGUA_real (real permission attempts) | PGE_real (executed) | MissingObj (nonexistent object) | UAR (unintended executed) |
|---|---|---|---|---|---|---|
| A-Ctx | 400 | 0.440 [0.39,0.49] | 0.297 [0.25,0.34] | 0.297 [0.25,0.34] | 0.065 [0.04,0.09] | 0.113 [0.09,0.15] |
| B-Ctx-Stop | 400 | 0.345 [0.30,0.39] | 0.287 [0.25,0.33] | 0.000 [0.00,0.01] | 0.058 [0.04,0.08] | 0.105 [0.08,0.14] |
| B-Ctx-Feedback | 400 | 0.375 [0.33,0.42] | 0.295 [0.25,0.34] | 0.000 [0.00,0.01] | 0.075 [0.05,0.11] | 0.122 [0.09,0.16] |
| C0 | 400 | 0.495 [0.45,0.54] | 0.282 [0.24,0.33] | 0.000 [0.00,0.01] | 0.052 [0.03,0.08] | 0.168 [0.13,0.21] |
| C | 400 | 0.983 [0.96,0.99] | 0.050 [0.03,0.08] | 0.000 [0.00,0.01] | 0.003 [0.00,0.01] | 0.015 [0.01,0.03] |

Held-out-template episodes (templates never seen in training), all available
| arm | n | TaskSuccess | PGUA_real (real permission attempts) | PGE_real (executed) | MissingObj (nonexistent object) | UAR (unintended executed) |
|---|---|---|---|---|---|---|
| A-Ctx | 29 | 0.621 [0.44,0.77] | 0.448 [0.28,0.62] | 0.448 [0.28,0.62] | 0.034 [0.01,0.17] | 0.276 [0.15,0.46] |
| B-Ctx-Stop | 131 | 0.496 [0.41,0.58] | 0.420 [0.34,0.51] | 0.000 [0.00,0.03] | 0.008 [0.00,0.04] | 0.221 [0.16,0.30] |
| B-Ctx-Feedback | 131 | 0.580 [0.49,0.66] | 0.412 [0.33,0.50] | 0.000 [0.00,0.03] | 0.061 [0.03,0.12] | 0.328 [0.25,0.41] |
| C0 | 131 | 0.382 [0.30,0.47] | 0.534 [0.45,0.62] | 0.000 [0.00,0.03] | 0.046 [0.02,0.10] | 0.344 [0.27,0.43] |
| C | 131 | 0.931 [0.87,0.96] | 0.214 [0.15,0.29] | 0.000 [0.00,0.03] | 0.008 [0.00,0.04] | 0.069 [0.04,0.13] |

Note: PGE_real must be 0.000 for every gateway arm. Wilson 95% intervals. Small slices: read with care.
