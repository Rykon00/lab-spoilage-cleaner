# Lab Spoilage Cleaner

Science packs that spoil inside a lab leave their spoilage in the lab's trash slots, and in vanilla
only an inserter at every single lab gets it out. This mod takes it out for you and hands it to your
logistic network.

## Modes (map setting)

| Mode | What happens |
|---|---|
| Robots pick it up (default) | The spoilage is dropped next to the lab and marked for deconstruction. Construction robots carry it to a storage chest. Only labs inside the construction area of one of your roboport networks are cleaned, so nothing is dropped where no robot can reach it. |
| Directly into the logistic network | The spoilage goes straight into the logistic network the lab stands in (storage chests). Labs outside logistic areas are not cleaned. |

Labs on space platforms (no robots there) put their spoilage into the platform hub.

The mod also takes items out of the lab input slots that the lab cannot use. Science packs the lab
can still use are never touched, and when a spoiled pack turns into another science pack, that pack
stays as well.

## Settings (map)

| Setting | Default | |
|---|---|---|
| `lsc-mode` | Robots pick it up | See above. |
| `lsc-interval` | 2 | Seconds between two checks of the same lab. The labs are spread over the ticks of the interval. |
| `lsc-platform-hub` | on | Labs on space platforms put their spoilage into the hub. |

Console command `/lsc-clean` cleans every lab right now.

## Compatibility

Requires Factorio 2.1. Works with and without Space Age; without spoilable science packs there is
just nothing to clean. Works with labs added by other mods (every entity of type `lab`). Can be added
to and removed from existing saves.

## Build

```
python tools/build.py   # -> dist/lab-spoilage-cleaner_<version>.zip
```
