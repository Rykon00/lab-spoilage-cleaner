-- Lab Spoilage Cleaner: empties the lab trash (spoil results of science packs that spoiled in the lab) and takes
-- items the lab cannot use out of its input slots, and hands them to the logistic network.
--
-- Mode "robots": the items are dropped next to the lab and marked for deconstruction, so construction robots
-- carry them to a storage chest. Only done when the lab is inside the construction area of a logistic network
-- of its force, so nothing is dropped where no robot can pick it up.
-- Mode "network": the items are put directly into the logistic network the lab stands in (storage chests).
-- Labs on space platforms (no robots there) put the items into the platform hub.
--
-- Labs are visited in turns: every tick a few of them, so each lab is checked about once per interval.

local function interval_ticks()
  return math.max(1, settings.global["lsc-interval"].value * 60)
end

local function mode()
  return settings.global["lsc-mode"].value
end

local function init_storage()
  storage.labs = storage.labs or {}       -- array of lab entities
  storage.cursor = storage.cursor or 1
  storage.accepts = {}                     -- lab prototype name -> set of accepted inputs (rebuilt on load)
end

local function add_lab(entity)
  if not (entity and entity.valid and entity.type == "lab") then return end
  storage.labs[#storage.labs + 1] = entity
end

local function rescan()
  storage.labs = {}
  storage.cursor = 1
  for _, surface in pairs(game.surfaces) do
    for _, lab in pairs(surface.find_entities_filtered{type = "lab"}) do add_lab(lab) end
  end
end

local function accepted_inputs(prototype)
  local set = storage.accepts[prototype.name]
  if not set then
    set = {}
    for _, name in pairs(prototype.lab_inputs or {}) do set[name] = true end
    storage.accepts[prototype.name] = set
  end
  return set
end

-- Where the items of this lab go (mode_override: "robots"/"network", default from the setting). Returns a function(stack) -> removed count, or nil if there is no target.
local function target_for(lab, mode_override)
  local surface = lab.surface
  local force = lab.force

  if surface.platform then
    if not settings.global["lsc-platform-hub"].value then return nil end
    local hub = surface.platform.hub
    if not (hub and hub.valid) then return nil end
    return function(stack) return hub.insert(stack) end
  end

  if (mode_override or mode()) == "network" then
    local network = surface.find_logistic_network_by_position(lab.position, force)
    if not network then return nil end
    return function(stack) return network.insert(stack) end
  end

  local networks = surface.find_logistic_networks_by_construction_area(lab.position, force)
  if not (networks and networks[1]) then return nil end
  return function(stack)
    local count = stack.count
    surface.spill_item_stack{
      position = lab.position,
      stack = stack,
      force = force, -- marks the dropped items for deconstruction: robots pick them up
      allow_belts = false,
      drop_full_stack = false, -- one item per entity: several robots work in parallel (a robot takes 1 item of a ground stack per trip)
    }
    return count
  end
end

-- Inventories to empty: the lab's trash (where the engine puts the spoil result of science packs that spoil
-- inside the lab) completely, the input slots only for items the lab cannot use.
local INVENTORIES = {
  {id = defines.inventory.lab_trash, all = true},
  {id = defines.inventory.lab_input, all = false},
}

-- Moves the unusable items out of one lab. Returns the number of items removed.
local function clean_lab(lab, mode_override)
  local target
  local removed = 0
  for _, spec in ipairs(INVENTORIES) do
    local inventory = spec.id and lab.get_inventory(spec.id)
    if inventory and not inventory.is_empty() then
      local accepts = (not spec.all) and accepted_inputs(lab.prototype)
      for i = 1, #inventory do
        local stack = inventory[i]
        if stack.valid_for_read and (spec.all or not accepts[stack.name]) then
          if target == nil then target = target_for(lab, mode_override) or false end
          if not target then return removed end
          local moved = target(stack)
          if moved and moved > 0 then
            if stack.valid_for_read then
              if moved >= stack.count then stack.clear() else stack.count = stack.count - moved end
            end
            removed = removed + moved
          end
        end
      end
    end
  end
  return removed
end

local function on_tick()
  local labs = storage.labs
  local count = #labs
  if count == 0 then return end
  local per_tick = math.ceil(count / interval_ticks())
  local cursor = storage.cursor
  for _ = 1, per_tick do
    if cursor > #labs then cursor = 1 end
    if #labs == 0 then break end
    local lab = labs[cursor]
    if lab.valid then
      clean_lab(lab)
      cursor = cursor + 1
    else
      -- swap-remove the dead entry and check the moved one in its place
      labs[cursor] = labs[#labs]
      labs[#labs] = nil
    end
  end
  storage.cursor = cursor
end

local function on_built(event)
  add_lab(event.entity)
end

local built_events = {
  defines.events.on_built_entity,
  defines.events.on_robot_built_entity,
  defines.events.on_space_platform_built_entity,
  defines.events.script_raised_built,
  defines.events.script_raised_revive,
  defines.events.on_entity_cloned,
}
local filter = {{filter = "type", type = "lab"}}
for _, id in pairs(built_events) do
  if id == defines.events.on_entity_cloned then
    script.on_event(id, function(event) add_lab(event.destination) end, filter)
  else
    script.on_event(id, on_built, filter)
  end
end

script.on_init(function()
  init_storage()
  rescan()
end)

script.on_configuration_changed(function()
  init_storage()
  rescan()
end)

script.on_event(defines.events.on_tick, on_tick)

-- /lsc-clean: clean every lab right now (for example after adding the mod to a save).
commands.add_command("lsc-clean", {"lsc.command-help"}, function(cmd)
  local total = 0
  for _, lab in pairs(storage.labs) do
    if lab.valid then total = total + clean_lab(lab) end
  end
  local player = cmd.player_index and game.get_player(cmd.player_index)
  local msg = {"lsc.cleaned", total}
  if player then player.print(msg) else game.print(msg) end
end)

-- Interface for the functional test and other mods.
remote.add_interface("lab-spoilage-cleaner", {
  clean_lab = function(lab, mode_override) return clean_lab(lab, mode_override) end,
  lab_count = function() return #storage.labs end,
})
