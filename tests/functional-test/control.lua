-- Functional test for lab-spoilage-cleaner, run by tools/load_check.py --test-mod tests/functional-test.
-- Lets agricultural science packs spoil inside labs and checks where the spoilage ends up:
--   A  lab in a roboport's construction area (mode robots): lab emptied, robots carry the spoilage to storage
--   B  lab without any logistic network: spoilage stays in the lab, nothing dropped
--   C  untracked lab, cleaned via remote call with mode "network": spoilage directly in the storage chest
--   D  lab on a space platform: spoilage goes into the hub
-- Usable science packs must stay in every lab. Writes "[functional-test] PASS|FAIL ..." and ends with DONE.

local TAG = "[functional-test] "
local SETUP = 10
local CHECK_LABS = SETUP + 600
local CHECK_NETWORK = SETUP + 3000
local SPOIL = "agricultural-science-pack"
local KEEP = "automation-science-pack"
local N = 5

local function pass(msg) log(TAG .. "PASS " .. msg) end
local function fail(msg) log(TAG .. "FAIL " .. msg) end
local function check(ok, msg) if ok then pass(msg) else fail(msg) end end

local function prepare(surface, area, tile)
  for _, e in pairs(surface.find_entities_filtered{area = area}) do
    if e.valid and e.type ~= "character" and e.name ~= "space-platform-hub" then e.destroy() end
  end
  local tiles = {}
  for x = area[1][1], area[2][1] - 1 do
    for y = area[1][2], area[2][2] - 1 do tiles[#tiles + 1] = {name = tile, position = {x, y}} end
  end
  surface.set_tiles(tiles)
end

local function power(surface, force, pos)
  local eei = surface.create_entity{name = "electric-energy-interface", position = {pos[1] + 2, pos[2]}, force = force}
  eei.electric_buffer_size = 1e10
  eei.power_production = 1e9
  eei.energy = 1e10
  surface.create_entity{name = "substation", position = pos, force = force}
end

-- A lab with N packs that spoil within a few ticks and N packs that stay usable.
local function spoiling_lab(surface, force, pos, raise)
  local lab = surface.create_entity{name = "lab", position = pos, force = force, raise_built = raise}
  if not lab then return nil end
  lab.insert{name = KEEP, count = N}
  lab.insert{name = SPOIL, count = N}
  local inv = lab.get_inventory(defines.inventory.lab_input)
  for i = 1, #inv do
    local s = inv[i]
    if s.valid_for_read and s.name == SPOIL then s.spoil_percent = 0.9999 end
  end
  return lab
end

-- Items of that name in the lab (input slots + trash, where the engine puts the spoil result).
local function in_lab(lab, name)
  return lab.get_inventory(defines.inventory.lab_input).get_item_count(name)
       + lab.get_inventory(defines.inventory.lab_trash).get_item_count(name)
end

local t = {}

local function setup()
  if not script.active_mods["space-age"] then
    pass("skipped: needs Space Age (spoilable science packs)")
    log(TAG .. "DONE")
    t.done = true
    return
  end
  local surface = game.surfaces.nauvis
  local force = game.forces.player
  surface.always_day = true

  -- A: roboport network with construction robots and a storage chest.
  prepare(surface, {{-30, -30}, {30, 30}}, "lab-dark-1")
  power(surface, force, {6, 0})
  local roboport = surface.create_entity{name = "roboport", position = {0, 0}, force = force}
  roboport.insert{name = "construction-robot", count = 10}
  t.chest_a = surface.create_entity{name = "storage-chest", position = {3, -6}, force = force}
  t.lab_a = spoiling_lab(surface, force, {-12, 12}, true)

  -- B: no network anywhere near.
  prepare(surface, {{290, -10}, {310, 10}}, "lab-dark-1")
  t.lab_b = spoiling_lab(surface, force, {300, 0}, true)

  -- C: separate network, lab not tracked by the mod (created without raise_built), cleaned by remote call.
  prepare(surface, {{-30, 170}, {30, 230}}, "lab-dark-1")
  power(surface, force, {6, 200})
  surface.create_entity{name = "roboport", position = {0, 200}, force = force}
  t.chest_c = surface.create_entity{name = "storage-chest", position = {3, 194}, force = force}
  t.lab_c = spoiling_lab(surface, force, {-6, 206}, false)

  -- D: space platform.
  local ok, err = pcall(function()
    local platform = force.create_space_platform{name = "lsc-test", planet = "nauvis",
                                                 starter_pack = "space-platform-starter-pack"}
    platform.apply_starter_pack()
    t.platform = platform
    t.hub = platform.hub
    local ps = platform.surface
    local tiles = {}
    for x = -12, 11 do for y = -12, 11 do tiles[#tiles + 1] = {name = "space-platform-foundation", position = {x, y}} end end
    ps.set_tiles(tiles)
    t.lab_d = spoiling_lab(ps, force, {0, 8}, true)
  end)
  check(ok and t.lab_d ~= nil and t.hub ~= nil, "space platform lab created" .. (ok and "" or (": " .. tostring(err))))

  check(remote.call("lab-spoilage-cleaner", "lab_count") >= 3, "built labs are tracked")
  for k, lab in pairs({A = t.lab_a, B = t.lab_b, C = t.lab_c}) do
    check(lab ~= nil, "lab " .. k .. " created")
  end
end

local function check_labs()
  -- the packs must have spoiled inside the labs
  check(in_lab(t.lab_b, "spoilage") == N, "B: spoilage stays in a lab without network (" .. in_lab(t.lab_b, "spoilage") .. ")")
  check(#game.surfaces.nauvis.find_entities_filtered{area = {{290, -10}, {310, 10}}, type = "item-entity"} == 0,
        "B: nothing dropped on the ground")

  check(in_lab(t.lab_a, "spoilage") == 0, "A: spoilage removed from lab (" .. in_lab(t.lab_a, "spoilage") .. " left)")
  check(in_lab(t.lab_a, KEEP) == N, "A: usable science packs stay in the lab")

  check(in_lab(t.lab_c, "spoilage") == N, "C: untracked lab not touched by on_tick")
  local removed = remote.call("lab-spoilage-cleaner", "clean_lab", t.lab_c, "network")
  check(removed == N, "C: network mode removed " .. tostring(removed) .. " items")
  check(t.chest_c.get_item_count("spoilage") == N, "C: spoilage directly in the storage chest")
  check(in_lab(t.lab_c, KEEP) == N, "C: usable science packs stay in the lab")

  if t.lab_d then
    check(in_lab(t.lab_d, "spoilage") == 0, "D: spoilage removed from platform lab")
    check(t.hub.get_item_count("spoilage") == N, "D: spoilage in the platform hub (" .. t.hub.get_item_count("spoilage") .. ")")
    check(in_lab(t.lab_d, KEEP) == N, "D: usable science packs stay in the platform lab")
  end
end

local function check_network()
  check(t.chest_a.get_item_count("spoilage") == N,
        "A: robots carried the spoilage to the storage chest (" .. t.chest_a.get_item_count("spoilage") .. ")")
  check(#game.surfaces.nauvis.find_entities_filtered{area = {{-30, -30}, {30, 30}}, type = "item-entity"} == 0,
        "A: no spoilage left on the ground")
  log(TAG .. "DONE")
end

script.on_event(defines.events.on_tick, function(event)
  if t.done then return end
  local tick = event.tick
  if tick == SETUP then setup()
  elseif tick == CHECK_LABS then check_labs()
  elseif tick == CHECK_NETWORK then check_network(); t.done = true end
end)
