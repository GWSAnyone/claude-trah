# Раскладка каталога функций по назначению

Адаптировано из obra/superpowers-lab `finding-duplicate-functions`
(MIT, © 2025 Jesse Vincent). Агент `general-purpose`, `model: haiku`.

```
Read the function catalog at <DIR>/catalog.json. It is a JSON array of
{file, line, name, kind, lines, head}, where `head` is the first lines of the body.

Assign EVERY function to exactly ONE category by its primary PURPOSE — what it
does, not how. Two functions that do the same job must land in the same
category even when their names and code differ: that is the whole point.

Categories (a Minecraft-compatible game engine in Rust: vanilla-exact world
generation, deterministic tick, wgpu renderer, network protocol, UI toolkit,
WASM mod host):

- vanilla-math: floor, clamp, lerp, wrap degrees, Java min/max, hashing of ids
- rng: random sources, shuffles, weighted picks, seeds and salts
- resource-id: `namespace:path` parsing, tags `#…`, registry lookups by name
- pack-data: reading JSON/NBT from the content pack, field extraction, error wrapping
- worldgen-noise: noise, density functions, samplers, caches of samples
- worldgen-place: features, structures, pieces, placement, block setting in a chunk
- world-storage: sections, columns, keys, save/load, journal, compression
- codec: byte readers/writers, cursors, varints, encode/decode of messages
- net: connections, links, queues, windows, acks
- sim-tick: scheduler, phases, owners, inputs, physics steps
- render-gpu: wgpu buffers, bind groups, pipelines, textures, allocators
- render-geometry: meshing, quads, UV mapping, culling, occlusion
- ui: screens, widgets, layout, text, input focus, scroll
- mod-host: WASM engine config, module scanning, host calls
- commands: command parsing, selectors, arguments
- app-shell: window creation, event loop, reporting, settings
- other: none of the above — say what in `purpose`

Output one object per function:
{"file": "...", "line": N, "name": "...", "category": "...", "purpose": "one specific sentence"}

Use the Write tool to save the COMPLETE JSON array to <DIR>/categorized.json.
Do not truncate, do not summarise, do not skip "obvious" ones — every entry of
the catalog must appear exactly once. Report only the count you wrote.
```
