data:extend({
  {
    -- robots: drop next to the lab, marked for deconstruction (robots carry it away).
    -- network: insert directly into the logistic network the lab stands in.
    type = "string-setting",
    name = "lsc-mode",
    setting_type = "runtime-global",
    default_value = "robots",
    allowed_values = {"robots", "network"},
    order = "a",
  },
  {
    -- Seconds between two checks of the same lab.
    type = "int-setting",
    name = "lsc-interval",
    setting_type = "runtime-global",
    default_value = 2,
    minimum_value = 1,
    maximum_value = 60,
    order = "b",
  },
  {
    -- Labs on space platforms put their spoilage into the platform hub.
    type = "bool-setting",
    name = "lsc-platform-hub",
    setting_type = "runtime-global",
    default_value = true,
    order = "c",
  },
})
