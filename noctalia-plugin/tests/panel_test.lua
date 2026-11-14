local controls
local pending
local commands = {}
local encoded
local notification
local timeout
local accepted = true
local closed = false
local choosers = { zenity = true, kdialog = true }
local files = {}
local failRead = false
local failRename = false
local statePath = "/backup/section-expansion.json"

local function copy(source)
  local result = {}
  for key, value in pairs(source) do result[key] = value end
  return result
end

ui = {}
for _, kind in ipairs({ "column", "row", "scroll", "label", "input", "button", "select", "separator" }) do
  ui[kind] = function(props, children) return { kind = kind, props = props, children = children or {} } end
end
panel = { render = function(tree) controls = tree end, close = function() closed = true end }
noctalia = {
  pluginDir = function() return "/plugin" end,
  pluginDataDir = function() return "/backup" end,
  listDir = function()
    return files[statePath] and { "section-expansion.json" } or {}
  end,
  readFile = function(path)
    if failRead then return nil, "read failed" end
    if files[path] then return "stored-state" end
    return nil, "missing"
  end,
  writeFile = function(path)
    files[path] = copy(encoded)
    return true
  end,
  renameFile = function(from, to)
    if failRename then return false, "rename failed" end
    files[to] = files[from]
    files[from] = nil
    return true
  end,
  fileExists = function(path) return files[path] ~= nil end,
  removeFile = function(path) files[path] = nil; return true end,
  notify = function(_, message) notification = message end,
  string = { trim = function(value) return value:match("^%s*(.-)%s*$") end },
  commandExists = function(name) return choosers[name] or false end,
  getenv = function(name) if name == "HOME" then return "/home/test" end end,
  fileInfo = function(path)
    if path == "/home/test/Documents" or path == "/home/test/New folder"
        or path == "/home/test2/Other" or path == "/tmp/bad$folder" then
      return { isDir = true }
    end
  end,
  runAsync = function(command, callback, timeoutMs)
    table.insert(commands, command)
    pending = callback
    timeout = timeoutMs
    return accepted
  end,
  json = {
    encode = function(value)
      if type(value) == "string" then return string.format("%q", value) end
      encoded = value
      return "encoded"
    end,
    decode = function(value)
      if value == "stored-state" then return copy(files[statePath]) end
      if value == "launcher-ok" then return {} end
      if value == "initial" then return { revision = "old", values = { DOCUMENTS = "$HOME/Documents" } } end
      if value == "saved" then return { revision = "new", values = { DOCUMENTS = "$HOME/Work" } } end
      if value == "apps" then return {
        revision = "apprev", roles = { ["Web browser"] = "<multiple>" },
        mimes = { ["application/json"] = "old.desktop" },
        apps = { { id = "browser.desktop", name = "Browser" } },
        role_mimes = { "text/html" },
      } end
      if value == "extension" then return { mime = "application/pdf-test" } end
      if value == "keybinds" then return {
        path = "/config.toml", revision = "keyrev", lock_revision = "lockrev", groups = { "Work" },
        bindings = {
          { key = "Mod+A", value = "window-close", mode = "action", group = "Work", locked = false, editable = true },
          { key = "Mod+B", value = "spawn app", mode = "action", group = "Work", locked = true, editable = true },
          { key = "Mod+C", value = '{ action = "window-close", repeat = true }', mode = "toml", group = "", locked = false, editable = true },
        },
      } end
      if value == "[]" then return {} end
      if value == '["one"]' then return { "one" } end
      if value == '["two"]' then return { "two" } end
      if value == "general" then
        local values = {}
        for _, key in ipairs({
          "general.autostart", "general.mod_key", "general.show_cheatsheet",
          "general.focus_on_activate", "general.attach_modal_dialogs", "general.honor_restored_maximize",
          "general.nvidia_sync_workaround", "general.xwayland", "general.xwayland_native_resolution",
          "general.xwayland_xsettings", "general.xwayland_primary_output", "events.lid_close",
          "events.lid_open", "screencast.disable_dynamic_confirmation", "drm.ignored_devices",
          "drm.ignored_pci_addresses", "include.files", "include.optional.files",
        }) do values[key] = { present = false, value = "" } end
        values["general.autostart"] = { present = true, value = '["one"]' }
        for _, key in ipairs({ "drm.ignored_devices", "drm.ignored_pci_addresses",
          "include.files", "include.optional.files" }) do values[key].value = "[]" end
        return { revision = "generalrev", path = "/config.toml", values = values }
      end
      return nil, "bad JSON"
    end,
  },
}

local function find(node, predicate)
  if predicate(node) then return node end
  for _, child in ipairs(node.children) do
    local result = find(child, predicate)
    if result then return result end
  end
end

local function button(text)
  return assert(find(controls, function(node) return node.kind == "button" and node.props.text == text end))
end

local function input(key)
  return assert(find(controls, function(node)
    return node.kind == "input" and node.props.key:match("^" .. key)
  end))
end

local function complete(stdout, exitCode, stderr)
  pending({ exitCode = exitCode or 0, stdout = stdout, stderr = stderr or "" })
end

local nativeRequire = require
require = function(name)
  if name == "./keybind_ui.luau" then return assert(loadfile(arg[2]))() end
  return nativeRequire(name)
end
assert(loadfile(arg[1]))()
onOpen()
assert(#commands == 0)
local header = controls.children[1]
assert(header.kind == "row" and header.children[1].props.flexGrow == 1)
assert(header.children[2].kind == "button" and header.children[2].props.text == "Close")
header.children[2].props.onClick()
assert(closed)
for index, child in ipairs(controls.children) do
  if child.kind == "button" and child.props.text == "Default Apps" then
    assert(controls.children[index + 1].kind == "separator")
    assert(controls.children[index + 2].props.text == "General")
  end
end
button("Open standalone app").props.onClick()
assert(commands[1][1] == "python3" and commands[1][2] == "/plugin/launch_app.py")
assert(timeout == 15000 and not button("Open standalone app").props.enabled)
complete("launcher-ok")
assert(button("Open standalone app").props.enabled)
assert(find(controls, function(node) return node.kind == "label" and node.props.text == "Launch request sent." end))
button("Open standalone app").props.onClick()
complete("", 1, "desktop entry missing")
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("desktop entry missing") end))
accepted = false
button("Open standalone app").props.onClick()
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("Could not start python3") end))
accepted = true
button("Open standalone app").props.onClick()
onClose()
complete("", 1, "launcher failed")
assert(notification:match("launcher failed"))
onOpen()
commands = {}
button("User Folders").props.onClick()
assert(commands[1][2] == "/plugin/user_dirs.py" and commands[1][3] == "read")
complete("initial")
assert(input("DOCUMENTS").props.value == "$HOME/Documents")
input("DOCUMENTS").props.onChange("$HOME/Work")
button("Back").props.onClick()
button("Default Apps").props.onClick()
assert(commands[2][2] == "/plugin/default_apps.py" and commands[2][3] == "read")
complete("apps")
assert(input("Web browser").props.value == "<multiple>")
assert(button("Common application roles").props.variant == "primary")
assert(button("Other file types").props.variant == "primary")
assert(find(controls, function(node) return node.kind == "separator" end))
assert(not find(controls, function(node) return node.kind == "input" and node.props.key == "search" end))
button("Common application roles").props.onClick()
assert(not find(controls, function(node) return node.kind == "input" and node.props.key:match("^Web browser") end))
button("Common application roles").props.onClick()
assert(input("Web browser").props.value == "<multiple>")
button("Other file types").props.onClick()
assert(input("application/json").props.value == "old.desktop")
button("Remove").props.onClick()
assert(not find(controls, function(node) return node.kind == "label" and node.props.text == "application/json" end))
input("new%-mime").props.onChange("application/json")
button("Add MIME type").props.onClick()
assert(input("application/json").props.value == "old.desktop")
local select = assert(find(controls, function(node)
  return node.kind == "select" and node.props.key == "select-Web browser"
end))
select.props.onChange("1")
assert(input("Web browser").props.value == "browser.desktop")
input("application/json").props.onChange("json.desktop")
button("Common application roles").props.onClick()
button("Other file types").props.onClick()
assert(not find(controls, function(node) return node.kind == "input" and node.props.key:match("^application/json") end))
button("Common application roles").props.onClick()
button("Other file types").props.onClick()
assert(input("Web browser").props.value == "browser.desktop")
assert(input("application/json").props.value == "json.desktop")
input("new%-mime").props.onChange(".pdf")
button("Other file types").props.onClick()
button("Other file types").props.onClick()
assert(input("new%-mime").props.value == ".pdf")
button("Add file extension").props.onClick()
assert(commands[3][3] == "extension" and commands[3][4] == ".pdf")
complete("extension")
input("application/pdf%-test").props.onChange("pdf.desktop")
button("Other file types").props.onClick()
button("Save").props.onClick()
assert(commands[4][3] == "save" and commands[4][4] == "apprev")
local found = {}
for _, item in ipairs(encoded) do found[item.key] = item.value end
assert(found["Web browser"] == "browser.desktop")
assert(found["application/json"] == "json.desktop")
assert(found["application/pdf-test"] == "pdf.desktop")
complete("", 1, "conflict")
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("conflict") end))
button("Back").props.onClick()
button("User Folders").props.onClick()
assert(input("DOCUMENTS").props.value == "$HOME/Work")
button("Save").props.onClick()
assert(encoded.DOCUMENTS == "$HOME/Work")
assert(commands[5][3] == "save" and commands[5][4] == "old" and commands[5][5] == "/backup")
complete("saved")
button("Save").props.onClick()
assert(#commands == 5)
input("DOCUMENTS").props.onChange("/new")
button("Save").props.onClick()
local previousSave = pending
onClose()
onOpen()
button("User Folders").props.onClick()
complete("initial")
previousSave({ exitCode = 1, stdout = "", stderr = "failed" })
assert(notification:match("failed"))
assert(input("DOCUMENTS").props.value == "$HOME/Documents")

local function browse(key)
  return assert(find(controls, function(node)
    return node.kind == "button" and node.props.key == "browse-" .. key
  end))
end

browse("DOCUMENTS").props.onClick()
assert(commands[#commands][1] == "zenity")
assert(commands[#commands][5] == "--filename=/home/test/Documents/")
assert(timeout == 60000 and not button("Save").props.enabled)
complete("/home/test/New folder\n")
assert(input("DOCUMENTS").props.value == "$HOME/New folder")
browse("DOCUMENTS").props.onClick()
complete("", 1)
assert(input("DOCUMENTS").props.value == "$HOME/New folder")
choosers.zenity = false
browse("DOCUMENTS").props.onClick()
assert(commands[#commands][1] == "kdialog" and commands[#commands][3] == "/home/test/New folder")
complete("/home/test2/Other\n")
assert(input("DOCUMENTS").props.value == "/home/test2/Other")
browse("DOCUMENTS").props.onClick()
complete("/tmp/bad$folder\n")
assert(input("DOCUMENTS").props.value == "/home/test2/Other")
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("unsupported") end))
browse("DOCUMENTS").props.onClick()
pending({ exitCode = 1, stdout = "", stderr = "", timedOut = true })
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("timed out") end))
accepted = false
browse("DOCUMENTS").props.onClick()
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("Could not start") end))
accepted = true
choosers.kdialog = false
local count = #commands
browse("DOCUMENTS").props.onClick()
assert(#commands == count)
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("Install zenity") end))
choosers.zenity = true
browse("DOCUMENTS").props.onClick()
local previousBrowse = pending
onClose()
onOpen()
button("User Folders").props.onClick()
complete("initial")
previousBrowse({ exitCode = 0, stdout = "/home/test/New folder\n", stderr = "" })
assert(input("DOCUMENTS").props.value == "$HOME/Documents")

button("Back").props.onClick()
button("General").props.onClick()
assert(commands[#commands][2] == "/plugin/general.py" and commands[#commands][3] == "read")
complete("general")
assert(input("general%-path").props.value == "/config.toml")
for _, title in ipairs({ "Session", "XWayland (restart)", "Lid events", "Screencast",
  "DRM devices (restart)", "Includes" }) do assert(button(title)) end
assert(input("general%.autostart%-1").props.value == "one")
input("general%.autostart%-1").props.onChange("two")
local toggle = assert(find(controls, function(node)
  return node.kind == "select" and node.props.key == "general-general.show_cheatsheet"
end))
toggle.props.onChange("2")
local modEnabled = assert(find(controls, function(node)
  return node.kind == "select" and node.props.key == "general-enabled-general.mod_key"
end))
modEnabled.props.onChange("1")
local modChoice = assert(find(controls, function(node)
  return node.kind == "select" and node.props.key == "general-mod-key-choice"
end))
modChoice.props.onChange("2")
assert(input("general%.mod_key").props.value == "Alt")
button("Session").props.onClick()
assert(not find(controls, function(node) return node.kind == "input" and node.props.key:match("^general%.autostart") end))
button("Session").props.onClick()
assert(input("general%.autostart%-1").props.value == "two")
button("Back").props.onClick()
button("General").props.onClick()
assert(input("general%.autostart%-1").props.value == "two")
input("general%-path").props.onChange("/other.toml")
local before = #commands
button("Save").props.onClick()
assert(#commands == before)
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("Reload the selected") end))
input("general%-path").props.onChange("/config.toml")
button("Save").props.onClick()
assert(commands[#commands][3] == "save" and commands[#commands][4] == "/config.toml")
assert(commands[#commands][5] == "generalrev" and timeout == 60000)
local generalChanges = {}
for _, change in ipairs(encoded) do generalChanges[change.key] = change end
assert(generalChanges["general.autostart"].value == '["two"]')
assert(generalChanges["general.show_cheatsheet"].present and generalChanges["general.show_cheatsheet"].value == "false")
assert(generalChanges["general.mod_key"].present and generalChanges["general.mod_key"].value == "Alt")
complete("general")

button("Session").props.onClick()
button("XWayland (restart)").props.onClick()
button("Back").props.onClick()
button("Default Apps").props.onClick()
complete("apps")
button("Common application roles").props.onClick()
button("Other file types").props.onClick()
onClose()
onOpen()
button("General").props.onClick()
complete("general")
assert(button("Session").props.glyph == "chevron-right")
assert(button("XWayland (restart)").props.glyph == "chevron-down")
button("Back").props.onClick()
button("Default Apps").props.onClick()
complete("apps")
assert(button("Common application roles").props.glyph == "chevron-right")
assert(button("Other file types").props.glyph == "chevron-down")

assert(loadfile(arg[1]))()
onOpen()
button("General").props.onClick()
complete("general")
assert(button("Session").props.glyph == "chevron-right")
assert(button("XWayland (restart)").props.glyph == "chevron-down")
failRename = true
button("XWayland (restart)").props.onClick()
assert(notification:match("Could not save section state"))
assert(files[statePath]["general:XWayland (restart)"] == true)
assert(files[statePath .. ".tmp"] == nil)
failRename = false
onClose()
failRead = true
onOpen()
assert(notification:match("Could not restore section states"))
button("General").props.onClick()
complete("general")
assert(button("Session").props.glyph == "chevron-right")
assert(button("XWayland (restart)").props.glyph == "chevron-right")
button("Session").props.onClick()
assert(notification:match("not saved"))
assert(files[statePath]["general:Session"] == false)
failRead = false

onClose()
onOpen()
button("Keybinds").props.onClick()
assert(commands[#commands][2] == "/plugin/keybinds.py" and commands[#commands][3] == "read")
complete("keybinds")
assert(button("Work (2)").props.glyph == "chevron-right")
button("Work (2)").props.onClick()
button("Mod+B (locked)").props.onClick()
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("Locked in Umbriel") end))
assert(not find(controls, function(node) return node.kind == "button" and node.props.text == "Remove keybind" end))
button("Mod+A").props.onClick()
input("keybind%-value").props.onChange("spawn editor")
button("Edit advanced options").props.onClick()
assert(input("keybind%-value").props.value == '{ action = "spawn editor" }')
input("keybind%-value").props.onChange('{ action = "spawn editor", repeat = false }')
input("keybind%-new%-key").props.onChange("Mod+D")
input("keybind%-new%-action").props.onChange("window-close")
button("Add keybind").props.onClick()
button("Remove keybind").props.onClick()
button("Restore keybind").props.onClick()
button("Back").props.onClick()
button("Keybinds").props.onClick()
assert(input("keybind%-value").props.value == "window-close")
button("Save").props.onClick()
assert(commands[#commands][2] == "/plugin/keybinds.py" and commands[#commands][3] == "save")
assert(commands[#commands][4] == "/config.toml" and commands[#commands][5] == "keyrev")
assert(commands[#commands][6] == "lockrev" and timeout == 60000)
local keybindChanges = {}
for _, change in ipairs(encoded) do keybindChanges[change.key] = change end
assert(keybindChanges["Mod+A"].mode == "toml" and keybindChanges["Mod+A"].value:match("repeat = false"))
assert(keybindChanges["Mod+D"].mode == "action" and keybindChanges["Mod+D"].value == "window-close")
assert(not keybindChanges["Mod+B"])
complete("", 1, "conflict")
assert(find(controls, function(node) return node.kind == "label" and node.props.text:match("conflict") end))
onClose()
onOpen()
button("Keybinds").props.onClick()
complete("keybinds")
assert(button("Work (2)").props.glyph == "chevron-down")
