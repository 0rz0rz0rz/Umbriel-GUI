local keybinds = {}

function keybinds.accept(state, data)
  state.path = data.path
  state.loadedPath = data.path
  state.lockRevision = data.lock_revision
  state.groups = data.groups
  state.bindings = data.bindings
  state.selected = nil
  state.nextId = 0
  for _, binding in ipairs(state.bindings) do
    state.nextId = state.nextId + 1
    binding.id = state.nextId
    binding.originalValue = binding.value
    binding.originalMode = binding.mode
  end
end

function keybinds.changes(state)
  local changes = {}
  for _, binding in ipairs(state.bindings) do
    if binding.removed and not binding.isNew then
      table.insert(changes, { key = binding.key, remove = true, value = "" })
    elseif not binding.removed and (binding.isNew or binding.value ~= binding.originalValue
        or binding.mode ~= binding.originalMode) then
      table.insert(changes, {
        key = binding.key, remove = false, mode = binding.mode, value = binding.value,
      })
    end
  end
  return changes
end

local function canonical(key)
  return string.lower(noctalia.string.trim(key)):gsub("%s+", " ")
end

function keybinds.rows(state, render, expansion, saveExpansion)
  local rows = {}
  table.insert(rows, ui.input({
    key = "keybind-search", value = state.search, fontSize = 12,
    placeholder = "Search shortcuts or actions", enabled = not state.busy,
    onChange = function(value) state.search = value; render() end,
  }))
  table.insert(rows, ui.label({ text = "Add a shortcut", fontSize = 12 }))
  table.insert(rows, ui.input({
    key = "keybind-new-key-" .. state.generation, value = state.newKey, fontSize = 12,
    placeholder = "Shortcut, e.g. Mod+Shift+Q", enabled = not state.busy,
    onChange = function(value) state.newKey = value end,
  }))
  table.insert(rows, ui.input({
    key = "keybind-new-action-" .. state.generation, value = state.newAction, fontSize = 12,
    placeholder = "Action, e.g. window-close or spawn firefox", enabled = not state.busy,
    onChange = function(value) state.newAction = value end,
  }))
  table.insert(rows, ui.button({ text = "Add keybind", fontSize = 12, enabled = not state.busy,
    onClick = function()
      local key, action = noctalia.string.trim(state.newKey), noctalia.string.trim(state.newAction)
      if key == "" or action == "" then
        state.status = "Enter both a shortcut and an action."
      else
        local duplicate = false
        for _, binding in ipairs(state.bindings) do
          if canonical(binding.key) == canonical(key) then duplicate = true; break end
        end
        if duplicate then
          state.status = "That shortcut is already listed."
        else
          state.nextId = state.nextId + 1
          local binding = { id = state.nextId, key = key, value = action, mode = "action",
            group = "", locked = false, editable = true, isNew = true }
          table.insert(state.bindings, binding)
          state.selected = binding
          state.newKey, state.newAction = "", ""
          state.generation = state.generation + 1
          state.status = "Keybind added. Press Save to apply."
        end
      end
      render()
    end,
  }))

  local selected = state.selected
  if selected then
    table.insert(rows, ui.separator({ spacing = 8 }))
    table.insert(rows, ui.label({ text = "Selected: " .. selected.key, fontSize = 14, fontWeight = "bold" }))
    if selected.locked then
      table.insert(rows, ui.label({ text = "Locked in Umbriel Settings. Unlock it there to edit.", fontSize = 12 }))
    elseif not selected.editable then
      table.insert(rows, ui.label({ text = "This TOML layout must be edited in the standalone app.", fontSize = 12 }))
    elseif selected.removed then
      table.insert(rows, ui.label({ text = "This keybind will be removed on Save.", fontSize = 12 }))
      table.insert(rows, ui.button({ text = "Restore keybind", fontSize = 12, enabled = not state.busy,
        onClick = function() selected.removed = false; state.generation = state.generation + 1; render() end }))
    else
      local advanced = selected.mode == "toml"
      table.insert(rows, ui.label({ text = advanced and "Action and options (TOML)" or "Action", fontSize = 12 }))
      table.insert(rows, ui.input({
        key = "keybind-value-" .. selected.id .. "-" .. state.generation, value = selected.value,
        fontSize = 12, multiline = advanced, height = advanced and 100 or nil, enabled = not state.busy,
        onChange = function(value) selected.value = value end,
      }))
      if not advanced then
        table.insert(rows, ui.button({ text = "Edit advanced options", fontSize = 12, enabled = not state.busy,
          onClick = function()
            local encoded, err = noctalia.json.encode(selected.value)
            if not encoded then
              state.status = "Could not encode action: " .. tostring(err)
            else
              selected.value = "{ action = " .. encoded .. " }"
              selected.mode = "toml"
              state.generation = state.generation + 1
            end
            render()
          end,
        }))
      end
      table.insert(rows, ui.button({ text = "Remove keybind", fontSize = 12, enabled = not state.busy,
        onClick = function() selected.removed = true; render() end }))
    end
  end

  table.insert(rows, ui.separator({ spacing = 8 }))
  local groups, seen = {}, {}
  for _, name in ipairs(state.groups) do
    if not seen[name] then table.insert(groups, name); seen[name] = true end
  end
  table.insert(groups, "")
  local search = string.lower(state.search)
  for _, group in ipairs(groups) do
    local matches = {}
    for _, binding in ipairs(state.bindings) do
      if binding.group == group and string.find(string.lower(binding.key .. " " .. binding.value), search, 1, true) then
        table.insert(matches, binding)
      end
    end
    if #matches > 0 then
      local title = group ~= "" and group or "Ungrouped"
      local expansionKey = "keybinds:group:" .. group
      local expanded = expansion[expansionKey] or false
      table.insert(rows, ui.button({
        key = expansionKey, text = title .. " (" .. #matches .. ")",
        glyph = expanded and "chevron-down" or "chevron-right",
        variant = "primary", fontSize = 14, glyphSize = 18, controlSize = "lg", contentAlign = "start",
        onClick = function() saveExpansion(expansionKey, not expanded); render() end,
      }))
      if expanded then
        for _, binding in ipairs(matches) do
          local label = binding.key
          if binding.locked then label = label .. " (locked)" end
          if binding.removed then label = label .. " (removed)" end
          table.insert(rows, ui.button({
            key = "keybind-item-" .. binding.id, text = label, fontSize = 12,
            contentAlign = "start", enabled = not state.busy,
            onClick = function() state.selected = binding; render() end,
          }))
        end
      end
    end
  end
  return rows
end

return keybinds
