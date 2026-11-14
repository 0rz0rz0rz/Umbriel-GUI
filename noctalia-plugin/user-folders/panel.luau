local keybinds = require("./keybind_ui.luau")

local folders = {
  { "DESKTOP", "Desktop" }, { "DOCUMENTS", "Documents" },
  { "DOWNLOAD", "Downloads" }, { "MUSIC", "Music" },
  { "PICTURES", "Pictures" }, { "VIDEOS", "Videos" },
  { "TEMPLATES", "Templates" }, { "PUBLICSHARE", "Public share" },
  { "PROJECTS", "Projects" },
}
local roles = {
  "Web browser", "Email client", "File manager", "Text editor",
  "Image viewer", "PDF viewer", "Audio player", "Video player",
}
local generalGroups = {
  { "Session", {
    { "general.autostart", "Autostart commands (restart)", "array", false },
    { "general.mod_key", "Mod key", "string", true },
    { "general.show_cheatsheet", "Show keybind cheatsheet at start", "bool", true },
    { "general.focus_on_activate", "Let activation requests focus windows", "bool", true },
    { "general.attach_modal_dialogs", "Attach modal dialogs to parent", "bool", true },
    { "general.honor_restored_maximize", "Honor maximize while opening", "bool", true },
    { "general.nvidia_sync_workaround", "NVIDIA sync workaround", "bool", true },
  } },
  { "XWayland (restart)", {
    { "general.xwayland", "Enable XWayland", "bool", true },
    { "general.xwayland_native_resolution", "Native resolution (sharp on scaled outputs)", "bool", true },
    { "general.xwayland_xsettings", "Announce scale/cursor via XSETTINGS", "bool", true },
    { "general.xwayland_primary_output", "Primary output for X11 apps", "string", true },
  } },
  { "Lid events", {
    { "events.lid_close", "Lid close command", "string", true },
    { "events.lid_open", "Lid open command", "string", true },
  } },
  { "Screencast", {
    { "screencast.disable_dynamic_confirmation", "Skip confirmation on target changes", "bool", true },
  } },
  { "DRM devices (restart)", {
    { "drm.ignored_devices", "Ignored device paths", "array", true },
    { "drm.ignored_pci_addresses", "Ignored PCI addresses", "array", true },
  } },
  { "Includes", {
    { "include.files", "Required include files", "array", true },
    { "include.optional.files", "Optional include files", "array", true },
  } },
}

local page = "menu"
local states = {}
local expansion = {}
local expansionPath
local openGeneration = 0
local launchState = { status = "" }
local render

local function loadExpansion()
  expansion = {}
  expansionPath = nil
  local dir, err = noctalia.pluginDataDir()
  local names
  if dir then names, err = noctalia.listDir(dir) end
  if not names then
    noctalia.notify("Umbriel-GUI", "Could not restore section states: " .. tostring(err or "unknown error") .. ". Sections start collapsed.")
    return
  end
  local path = dir .. "/section-expansion.json"
  local exists = false
  for _, name in ipairs(names) do
    if name == "section-expansion.json" then exists = true; break end
  end
  if exists then
    local raw
    raw, err = noctalia.readFile(path)
    local data
    if raw then data, err = noctalia.json.decode(raw) end
    if type(data) ~= "table" then
      noctalia.notify("Umbriel-GUI", "Could not restore section states: " .. tostring(err or "invalid data") .. ". Sections start collapsed.")
      return
    end
    for key, value in pairs(data) do
      if type(key) ~= "string" or type(value) ~= "boolean" then
        noctalia.notify("Umbriel-GUI", "Could not restore section states: invalid data. Sections start collapsed.")
        return
      end
    end
    expansion = data
  end
  expansionPath = path
end

local function saveExpansion(key, value)
  expansion[key] = value
  if not expansionPath then
    noctalia.notify("Umbriel-GUI", "Section state was not saved; persistent data could not be loaded.")
    return
  end
  local data, err = noctalia.json.encode(expansion)
  local temp = expansionPath .. ".tmp"
  local ok
  if data then ok, err = noctalia.writeFile(temp, data) end
  if ok then ok, err = noctalia.renameFile(temp, expansionPath) end
  if not ok then
    local cleanup = ""
    if noctalia.fileExists(temp) then
      local removed, removeError = noctalia.removeFile(temp)
      if not removed then cleanup = "; could not remove temporary file: " .. tostring(removeError) end
    end
    noctalia.notify("Umbriel-GUI", "Could not save section state: " .. tostring(err or "unknown error") .. cleanup)
  end
end

local function copy(source)
  local result = {}
  for key, value in pairs(source) do result[key] = value end
  return result
end

local function runHelper(state, script, args, done)
  local dir = noctalia.pluginDir()
  if not dir then
    state.status = "Could not locate the plugin directory."
    render()
    return
  end
  local command = { "python3", dir .. "/" .. script }
  for _, arg in ipairs(args) do table.insert(command, arg) end
  local requestGeneration = openGeneration
  state.busy = true
  render()
  local accepted = noctalia.runAsync(command, function(result)
    if requestGeneration ~= openGeneration then
      if args[1] == "save" then
        if result.exitCode == 0 and not result.timedOut and not result.stdoutTruncated and not result.stderrTruncated then
          noctalia.notify("Umbriel-GUI", "Save finished after closing. Reload the panel.")
        else
          noctalia.notify("Umbriel-GUI", "Save failed or timed out after closing. Reload and check the file.")
        end
      elseif script == "launch_app.py" and (result.exitCode ~= 0 or result.timedOut or result.stdoutTruncated or result.stderrTruncated) then
        noctalia.notify("Umbriel-GUI", "Could not confirm standalone launch: " .. (result.stderr ~= "" and result.stderr or "launcher failed or timed out"))
      end
      return
    end
    state.busy = false
    if result.timedOut or result.stdoutTruncated or result.stderrTruncated then
      state.status = "Helper timed out or its output was truncated. Reload before retrying."
    elseif result.exitCode ~= 0 then
      state.status = "Error: " .. (result.stderr ~= "" and result.stderr or "helper failed")
    else
      local data, err = noctalia.json.decode(result.stdout)
      if not data then
        state.status = "Invalid helper response: " .. tostring(err)
      else
        done(data)
      end
    end
    render()
  end, (script == "general.py" or script == "keybinds.py") and args[1] == "save" and 60000
    or script == "launch_app.py" and 15000 or nil)
  if not accepted then
    state.busy = false
    state.status = "Could not start python3. Install Python 3 and try again."
    render()
  end
end

local function acceptSnapshot(state, data, message)
  state.revision = data.revision
  state.generation = state.generation + 1
  state.status = message
  if page == "keybinds" then
    keybinds.accept(state, data)
  elseif page == "general" then
    state.path = data.path
    state.loadedPath = data.path
    state.values = data.values
    state.original = {}
    state.expanded = state.expanded or {}
    for _, group in ipairs(generalGroups) do
      local anyPresent = false
      for _, field in ipairs(group[2]) do
        local value = state.values[field[1]]
        state.original[field[1]] = { present = value.present, value = value.value }
        anyPresent = anyPresent or value.present
      end
      if state.expanded[group[1]] == nil then
        local saved = expansion["general:" .. group[1]]
        if saved == nil then saved = expansionPath ~= nil and anyPresent end
        state.expanded[group[1]] = saved
      end
    end
  elseif page == "folders" then
    state.values = data.values
    state.original = copy(data.values)
  else
    state.roles = data.roles
    state.originalRoles = copy(data.roles)
    state.mimes = data.mimes
    state.originalMimes = copy(data.mimes)
    state.removed = {}
    state.apps = data.apps
    state.roleMimes = data.role_mimes
  end
end

local function reload()
  local state = states[page]
  state.status = "Loading..."
  local script = page == "keybinds" and "keybinds.py" or page == "general" and "general.py"
    or page == "folders" and "user_dirs.py" or "default_apps.py"
  local args = { "read" }
  if (page == "general" or page == "keybinds") and state.path ~= "" then table.insert(args, state.path) end
  runHelper(state, script, args, function(data)
    acceptSnapshot(state, data, "Loaded. Changes are saved only when you press Save.")
  end)
end

local function save()
  local state = states[page]
  local changes = {}
  local changed = false
  if page == "keybinds" then
    if state.path ~= state.loadedPath then
      state.status = "Reload the selected config before saving."
      render()
      return
    end
    changes = keybinds.changes(state)
    changed = #changes > 0
  elseif page == "general" then
    if state.path ~= state.loadedPath then
      state.status = "Reload the selected config before saving."
      render()
      return
    end
    for _, group in ipairs(generalGroups) do
      for _, field in ipairs(group[2]) do
        local key = field[1]
        local value, original = state.values[key], state.original[key]
        if value.present ~= original.present or (value.present and value.value ~= original.value) then
          table.insert(changes, { key = key, present = value.present, value = value.value })
        end
      end
    end
    changed = #changes > 0
  elseif page == "folders" then
    for _, folder in ipairs(folders) do
      local key = folder[1]
      local value = state.values[key] or ""
      if value ~= (state.original[key] or "") then
        changes[key] = value
        changed = true
      end
    end
  else
    for _, role in ipairs(roles) do
      local value = state.roles[role] or ""
      if value ~= (state.originalRoles[role] or "") then
        table.insert(changes, { kind = "role", key = role, value = value })
      end
    end
    for mime, value in pairs(state.mimes) do
      if value ~= (state.originalMimes[mime] or "") then
        table.insert(changes, { kind = "mime", key = mime, value = value })
      end
    end
    changed = #changes > 0
  end
  if not changed then
    state.status = "No changes to save."
    render()
    return
  end
  local encoded, err = noctalia.json.encode(changes)
  if not encoded then
    state.status = "Could not encode changes: " .. tostring(err)
    render()
    return
  end
  local backup, backupError = noctalia.pluginDataDir()
  if not backup then
    state.status = "Could not access backup directory: " .. tostring(backupError)
    render()
    return
  end
  state.status = "Saving..."
  local script = page == "keybinds" and "keybinds.py" or page == "general" and "general.py"
    or page == "folders" and "user_dirs.py" or "default_apps.py"
  local args = { "save", state.revision, backup, encoded }
  if page == "general" then args = { "save", state.loadedPath, state.revision, backup, encoded } end
  if page == "keybinds" then args = { "save", state.loadedPath, state.revision, state.lockRevision, backup, encoded } end
  runHelper(state, script, args, function(data)
    local message = (page == "general" or page == "keybinds") and "Saved and validated. Restart where required."
      or "Saved. Restart applications to pick up changes."
    if data.warning and data.warning ~= "" then message = message .. " Warning: " .. data.warning end
    acceptSnapshot(state, data, message)
  end)
end

local function updateArray(field, values)
  local encoded = {}
  for _, item in ipairs(values) do
    local value, err = noctalia.json.encode(item)
    if not value then return nil, err end
    table.insert(encoded, value)
  end
  field.value = "[" .. table.concat(encoded, ", ") .. "]"
  return true
end

local function generalRows(state)
  local rows = {}
  for _, group in ipairs(generalGroups) do
    local title = group[1]
    table.insert(rows, ui.button({
      key = "general-group-" .. title, text = title,
      glyph = state.expanded[title] and "chevron-down" or "chevron-right",
      variant = "primary", fontSize = 14, glyphSize = 18, controlSize = "lg", contentAlign = "start",
      onClick = function()
        state.expanded[title] = not state.expanded[title]
        saveExpansion("general:" .. title, state.expanded[title])
        render()
      end,
    }))
    if state.expanded[title] then
      for _, spec in ipairs(group[2]) do
        local key, label, kind, optional = spec[1], spec[2], spec[3], spec[4]
        local field = state.values[key]
        local controls = { ui.label({ text = label, fontSize = 12 }) }
        if kind == "bool" then
          table.insert(controls, ui.select({
            key = "general-" .. key,
            options = { "Use default", "On", "Off" },
            selectedIndex = not field.present and 0 or field.value == "true" and 1 or 2,
            enabled = not state.busy,
            onChange = function(index)
              index = tonumber(index)
              field.present = index ~= 0
              field.value = index == 1 and "true" or "false"
              render()
            end,
          }))
        else
          if optional then
            table.insert(controls, ui.select({
              key = "general-enabled-" .. key,
              options = { "Use default", "Set value" },
              selectedIndex = field.present and 1 or 0, enabled = not state.busy,
              onChange = function(index) field.present = tonumber(index) == 1; render() end,
            }))
          end
          if not optional or field.present then
            if kind == "array" then
              local items, err = noctalia.json.decode(field.value)
              if not items then
                table.insert(controls, ui.label({ text = "Invalid list: " .. tostring(err), fontSize = 12 }))
              else
                for index, value in ipairs(items) do
                  table.insert(controls, ui.row({ gap = 6 }, {
                    ui.input({
                      key = key .. "-" .. index .. "-" .. state.generation,
                      value = value, fontSize = 12, flexGrow = 1, enabled = not state.busy,
                      onChange = function(text)
                        items[index] = text
                        local ok, errorMessage = updateArray(field, items)
                        if ok then field.present = true end
                        if not ok then state.status = "Could not encode list: " .. tostring(errorMessage); render() end
                      end,
                    }),
                    ui.button({ text = "Remove", fontSize = 12, enabled = not state.busy, onClick = function()
                      table.remove(items, index)
                      local ok, errorMessage = updateArray(field, items)
                      if ok then field.present = true end
                      if not ok then state.status = "Could not encode list: " .. tostring(errorMessage) end
                      state.generation = state.generation + 1
                      render()
                    end }),
                  }))
                end
                table.insert(controls, ui.button({ text = "Add", key = "add-" .. key, fontSize = 12,
                  enabled = not state.busy, onClick = function()
                    table.insert(items, "")
                    local ok, errorMessage = updateArray(field, items)
                    if ok then field.present = true end
                    if not ok then state.status = "Could not encode list: " .. tostring(errorMessage) end
                    state.generation = state.generation + 1
                    render()
                  end }))
              end
            else
              table.insert(controls, ui.input({
                key = key .. "-" .. state.generation, value = field.value, fontSize = 12, enabled = not state.busy,
                placeholder = key == "general.mod_key" and "Super, Alt, Ctrl, or Shift" or "",
                onChange = function(value) field.value = value end,
              }))
              if key == "general.mod_key" then
                local choices = { "Super", "Alt", "Ctrl", "Shift" }
                table.insert(controls, ui.select({
                  key = "general-mod-key-choice",
                  options = { "Choose mod key", "Super", "Alt", "Ctrl", "Shift" },
                  selectedIndex = 0, enabled = not state.busy,
                  onChange = function(index)
                    local choice = choices[tonumber(index) or 0]
                    if choice then
                      field.value = choice
                      state.generation = state.generation + 1
                      render()
                    end
                  end,
                }))
              end
            end
          end
        end
        table.insert(rows, ui.column({ key = "general-field-" .. key, gap = 4 }, controls))
      end
    end
    table.insert(rows, ui.separator({ spacing = 8 }))
  end
  return rows
end

local function appEditor(state, values, key)
  local options = { "Choose an installed application" }
  for _, app in ipairs(state.apps) do
    table.insert(options, app.name .. " (" .. app.id .. ")")
  end
  return ui.column({ gap = 4 }, {
    ui.input({
      key = key .. state.generation,
      fontSize = 12,
      value = values[key] or "",
      placeholder = "Desktop file ID (e.g. firefox.desktop)",
      enabled = not state.busy,
      onChange = function(value) values[key] = value end,
    }),
    ui.select({
      key = "select-" .. key,
      options = options,
      selectedIndex = 0,
      enabled = not state.busy and #state.apps > 0,
      onChange = function(index)
        local app = state.apps[tonumber(index) or 0]
        if app then
          values[key] = app.id
          state.generation = state.generation + 1
          render()
        end
      end,
    }),
  })
end

local function addMime(state, mime)
  mime = noctalia.string.trim(mime)
  if mime == "" then
    state.status = "Enter a MIME type or file extension."
    return
  end
  for existing in pairs(state.mimes) do
    if string.lower(existing) == string.lower(mime) then
      if state.removed[existing] then
        state.removed[existing] = nil
        state.mimes[existing] = state.originalMimes[existing] or ""
        state.newMime = ""
        state.generation = state.generation + 1
        state.status = "Association restored."
        return
      end
      state.status = "That MIME type is already listed."
      return
    end
  end
  for _, existing in ipairs(state.roleMimes) do
    if string.lower(existing) == string.lower(mime) then
      state.status = "That MIME type is managed by a common application role."
      return
    end
  end
  state.mimes[mime] = ""
  state.newMime = ""
  state.generation = state.generation + 1
  state.status = "Enter an application ID and press Save."
end

local function browseFolder(state, key, label)
  local chooser
  if noctalia.commandExists("zenity") then
    chooser = "zenity"
  elseif noctalia.commandExists("kdialog") then
    chooser = "kdialog"
  else
    state.status = "Install zenity or kdialog to browse for folders."
    render()
    return
  end

  local home = noctalia.getenv("HOME")
  local current = state.values[key] or ""
  if current == "$HOME" then
    current = home or ""
  elseif current:sub(1, 6) == "$HOME/" then
    current = home and (home .. current:sub(6)) or ""
  end
  local info = current ~= "" and noctalia.fileInfo(current) or nil
  local start = info and info.isDir and current or home
  local command
  if chooser == "zenity" then
    command = { "zenity", "--file-selection", "--directory", "--title=Choose " .. label .. " folder" }
    if start and start ~= "" then table.insert(command, "--filename=" .. start:gsub("/+$", "") .. "/") end
  else
    command = { "kdialog", "--getexistingdirectory" }
    if start and start ~= "" then table.insert(command, start) end
    table.insert(command, "--title")
    table.insert(command, "Choose " .. label .. " folder")
  end

  local requestGeneration = openGeneration
  state.busy = true
  state.status = "Choose a folder..."
  render()
  local accepted = noctalia.runAsync(command, function(result)
    if requestGeneration ~= openGeneration then return end
    state.busy = false
    if result.timedOut or result.stdoutTruncated or result.stderrTruncated then
      state.status = "Folder chooser timed out or its output was truncated."
    elseif result.exitCode == 1 and result.stdout == "" and result.stderr == "" then
      state.status = "Folder selection cancelled."
    elseif result.exitCode ~= 0 then
      state.status = "Folder chooser failed: " .. (result.stderr ~= "" and result.stderr or "unknown error")
    else
      local selected = result.stdout:gsub("\n$", ""):gsub("\r$", "")
      local selectedInfo = selected ~= "" and noctalia.fileInfo(selected) or nil
      if selected:sub(1, 1) ~= "/" or not selectedInfo or not selectedInfo.isDir then
        state.status = "Folder chooser did not return an existing absolute directory."
      else
        if home and home ~= "/" and (selected == home or selected:sub(1, #home + 1) == home .. "/") then
          selected = "$HOME" .. selected:sub(#home + 1)
        end
        local remainder = selected:sub(1, 5) == "$HOME" and selected:sub(6) or selected
        if remainder:find('[$`"\\\r\n%z]') then
          state.status = "Selected folder contains characters unsupported by user-dirs.dirs."
        else
          state.values[key] = selected
          state.generation = state.generation + 1
          state.status = "Folder selected. Press Save to apply."
        end
      end
    end
    render()
  end, 60000)
  if not accepted then
    state.busy = false
    state.status = "Could not start the folder chooser."
    render()
  end
end

local function folderRows(state)
  local rows = {}
  for _, folder in ipairs(folders) do
    local key, label = folder[1], folder[2]
    table.insert(rows, ui.column({ key = key, gap = 4 }, {
      ui.label({ text = label, fontSize = 12 }),
      ui.row({ gap = 8, align = "center" }, {
        ui.input({
          key = key .. state.generation,
          fontSize = 12,
          value = state.values[key] or "",
          placeholder = "Not set",
          flexGrow = 1,
          enabled = not state.busy,
          onChange = function(value) state.values[key] = value end,
        }),
        ui.button({
          key = "browse-" .. key,
          text = "Browse...",
          fontSize = 12,
          tooltip = "Browse " .. label .. " folder",
          enabled = not state.busy,
          onClick = function() browseFolder(state, key, label) end,
        }),
      }),
    }))
  end
  return rows
end

local function appRows(state)
  local rows = { ui.button({
    key = "common-application-roles",
    text = "Common application roles",
    glyph = state.rolesExpanded and "chevron-down" or "chevron-right",
    variant = "primary",
    fontSize = 14,
    glyphSize = 18,
    controlSize = "lg",
    contentAlign = "start",
    onClick = function()
      state.rolesExpanded = not state.rolesExpanded
      saveExpansion("apps:roles", state.rolesExpanded)
      render()
    end,
  }) }
  if state.rolesExpanded then
    for _, role in ipairs(roles) do
      table.insert(rows, ui.column({ key = role, gap = 4 }, {
        ui.label({ text = role, fontSize = 12 }),
        appEditor(state, state.roles, role),
      }))
    end
  end
  table.insert(rows, ui.separator({ spacing = 12 }))
  table.insert(rows, ui.button({
    key = "other-file-types",
    text = "Other file types",
    glyph = state.mimesExpanded and "chevron-down" or "chevron-right",
    variant = "primary",
    fontSize = 14,
    glyphSize = 18,
    controlSize = "lg",
    contentAlign = "start",
    onClick = function()
      state.mimesExpanded = not state.mimesExpanded
      saveExpansion("apps:mimes", state.mimesExpanded)
      render()
    end,
  }))
  if not state.mimesExpanded then return rows end
  table.insert(rows, ui.input({
    key = "search",
    fontSize = 12,
    value = state.search,
    placeholder = "Search MIME types or application IDs",
    onChange = function(value) state.search = value; render() end,
  }))
  local names = {}
  for mime in pairs(state.mimes) do table.insert(names, mime) end
  table.sort(names)
  for _, mime in ipairs(names) do
    local value = state.mimes[mime]
    if not state.removed[mime] and string.find(string.lower(mime .. " " .. value), string.lower(state.search), 1, true) then
      table.insert(rows, ui.column({ key = mime, gap = 4 }, {
        ui.row({ gap = 6 }, {
          ui.label({ text = mime, fontSize = 12, flexGrow = 1 }),
          ui.button({ text = "Remove", fontSize = 12, enabled = not state.busy, onClick = function()
            state.mimes[mime] = ""
            state.removed[mime] = true
            state.status = "The association will be removed when you save."
            render()
          end }),
        }),
        appEditor(state, state.mimes, mime),
      }))
    end
  end
  table.insert(rows, ui.input({
    key = "new-mime-" .. state.generation,
    fontSize = 12,
    value = state.newMime,
    placeholder = "MIME type or file extension",
    enabled = not state.busy,
    onChange = function(value) state.newMime = value end,
  }))
  table.insert(rows, ui.row({ gap = 6 }, {
    ui.button({ text = "Add MIME type", fontSize = 12, enabled = not state.busy, onClick = function()
      addMime(state, state.newMime)
      render()
    end }),
    ui.button({ text = "Add file extension", fontSize = 12, enabled = not state.busy, onClick = function()
      runHelper(state, "default_apps.py", { "extension", state.newMime }, function(data)
        addMime(state, data.mime)
      end)
    end }),
  }))
  return rows
end

render = function()
  if page == "menu" then
    panel.render(ui.column({ gap = 12, flexGrow = 1 }, {
      ui.row({ gap = 8 }, {
        ui.label({ text = "Umbriel-GUI", fontSize = 16, fontWeight = "bold", flexGrow = 1 }),
        ui.button({ text = "Close", fontSize = 12, onClick = function() panel.close() end }),
      }),
      ui.label({ text = "Choose a section", fontSize = 12 }),
      ui.button({ text = "User Folders", fontSize = 12, onClick = function() openSection("folders") end }),
      ui.button({ text = "Default Apps", fontSize = 12, onClick = function() openSection("apps") end }),
      ui.separator({ spacing = 8 }),
      ui.button({ text = "General", fontSize = 12, onClick = function() openSection("general") end }),
      ui.button({ text = "Keybinds", fontSize = 12, onClick = function() openSection("keybinds") end }),
      ui.button({ text = "Open standalone app", fontSize = 12, enabled = not launchState.busy, onClick = function()
        launchState.status = "Launching standalone app..."
        runHelper(launchState, "launch_app.py", {}, function() launchState.status = "Launch request sent." end)
      end }),
      ui.label({ text = launchState.status, fontSize = 12, maxLines = 3 }),
    }))
    return
  end
  local state = states[page]
  local rows = {}
  if state.revision then
    rows = page == "keybinds" and keybinds.rows(state, render, expansion, saveExpansion)
      or page == "general" and generalRows(state) or page == "folders" and folderRows(state) or appRows(state)
  end
  local title = page == "keybinds" and "Keybinds" or page == "general" and "General"
    or page == "folders" and "User Folders" or "Default Apps"
  local help = (page == "general" or page == "keybinds") and "Check the config path, then Reload. Includes are not resolved."
    or page == "folders" and "Use an absolute path or $HOME/path. Folders are not created."
    or "Choose an installed app or enter a desktop-file ID. Changes apply only on Save."
  if page == "general" or page == "keybinds" then
    table.insert(rows, 1, ui.column({ gap = 4 }, {
      ui.label({ text = "Umbriel config path", fontSize = 12 }),
      ui.input({
        key = "general-path-" .. state.generation, value = state.path, fontSize = 12,
        placeholder = "Path to Umbriel config", enabled = not state.busy,
        onChange = function(value) state.path = value end,
      }),
    }))
  end
  panel.render(ui.column({ gap = 10, flexGrow = 1 }, {
    ui.row({ gap = 8 }, {
      ui.button({ text = "Back", fontSize = 12, enabled = not state.busy, onClick = function() page = "menu"; render() end }),
      ui.label({ text = title, fontSize = 16, fontWeight = "bold", flexGrow = 1 }),
      ui.button({ text = "Close", fontSize = 12, onClick = function() panel.close() end }),
    }),
    ui.label({ text = help, fontSize = 12, maxLines = 2 }),
    ui.scroll({ gap = 10, flexGrow = 1 }, rows),
    ui.label({ text = state.status, fontSize = 12, maxLines = 3 }),
    ui.row({ gap = 8 }, {
      ui.button({ text = "Reload", fontSize = 12, enabled = not state.busy, onClick = reload }),
      ui.button({ text = "Save", fontSize = 12, variant = "primary", enabled = state.revision ~= nil and not state.busy, onClick = save }),
    }),
  }))
end

function openSection(section)
  page = section
  if not states[section] then
    local rolesExpanded = expansion["apps:roles"]
    if rolesExpanded == nil then rolesExpanded = expansionPath ~= nil end
    states[section] = {
      generation = 0, status = "Loading...", search = "", newMime = "",
      rolesExpanded = rolesExpanded, mimesExpanded = expansion["apps:mimes"] or false, path = "",
      newKey = "", newAction = "",
    }
    reload()
  else
    render()
  end
end

function onOpen()
  openGeneration = openGeneration + 1
  states = {}
  launchState = { status = "" }
  loadExpansion()
  page = "menu"
  render()
end

function onClose()
  openGeneration = openGeneration + 1
end
