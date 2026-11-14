local toggles = {}
local glyph, label, tooltip
barWidget = {
  setGlyph = function(value) glyph = value end,
  setText = function(value) label = value end,
  setTooltip = function(value) tooltip = value end,
}
noctalia = {
  togglePanel = function(value) table.insert(toggles, value) end,
}

assert(loadfile(arg[1]))()
assert(glyph == "settings" and label == "Umbriel-GUI" and tooltip ~= "")
onClick()
onClick()
assert(#toggles == 2)
assert(toggles[1] == "umbriel-settings/user-folders:folders" and toggles[2] == toggles[1])
