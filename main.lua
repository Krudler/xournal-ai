-- XournalAI Plugin — main.lua
-- Sends handwritten notes as image to Claude API and displays the response.

local CONFIG_PATH = os.getenv("HOME") .. "/.config/xournalpp-ai/settings.json"
local PLUGIN_PATH = nil  -- set in initUi

-- ---------------------------------------------------------------------------
-- Plugin registration
-- ---------------------------------------------------------------------------

function initUi()
  PLUGIN_PATH = debug.getinfo(1, "S").source:match("^@(.+)/[^/]+$")
  app.registerUi({menu = "Ask AI",      callback = "askAI",       accelerator = "<Control><Alt>a"})
  app.registerUi({menu = "AI Settings", callback = "showSettings", accelerator = ""})
end

-- ---------------------------------------------------------------------------
-- Settings
-- ---------------------------------------------------------------------------

local function loadSettings()
  local f = io.open(CONFIG_PATH, "r")
  if not f then return {} end
  local content = f:read("*a"); f:close()
  local key     = content:match('"api_key"%s*:%s*"([^"]+)"')
  local python  = content:match('"python_path"%s*:%s*"([^"]+)"')
  return {api_key = key, python_path = python}
end

-- ---------------------------------------------------------------------------
-- Debug logging
-- ---------------------------------------------------------------------------

local function log(msg)
  local f = io.open("/tmp/xai_debug.log", "a")
  if f then f:write(os.date("%H:%M:%S") .. " " .. msg .. "\n"); f:close() end
end

-- ---------------------------------------------------------------------------
-- Shell helpers
-- ---------------------------------------------------------------------------

local function shellEscape(s)
  return s:gsub("'", "'\\''")
end

-- ---------------------------------------------------------------------------
-- Settings dialog — delegates to Python GTK dialog for full-featured UI
-- ---------------------------------------------------------------------------

function showSettings()
  local settings = loadSettings()
  local python = settings.python_path or "python3"
  local script = PLUGIN_PATH .. "/helper/settings_dialog.py"
  -- Run synchronously (blocks Xournal briefly, but no clipboard deadlock risk)
  os.execute(string.format(
    "PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3 '%s' '%s'",
    shellEscape(script), shellEscape(CONFIG_PATH)
  ))
end

-- ---------------------------------------------------------------------------
-- Main entry point
-- ---------------------------------------------------------------------------

function askAI()
  log("askAI started")
  local settings = loadSettings()

  if not settings.api_key or settings.api_key == "" then
    app.msgbox("No API key set. Please configure it via Plugin > AI Settings.", {[1] = "OK"})
    return
  end

  -- Copy selection to clipboard NOW, while Xournal's main thread is still running.
  -- The clipboard will be read by the background orchestrator AFTER this callback returns,
  -- avoiding the clipboard deadlock.
  app.uiAction({action = "ACTION_COPY"})
  log("selection copied, launching orchestrator")

  local python = settings.python_path or "python3"
  local orchestrator = PLUGIN_PATH .. "/helper/capture_and_ask.py"
  local cmd = string.format(
    "'%s' '%s' '%s' '%s' &",
    shellEscape(python),
    shellEscape(orchestrator),
    shellEscape(CONFIG_PATH),
    shellEscape(PLUGIN_PATH)
  )
  os.execute(cmd)
  log("askAI done — orchestrator running in background")
end
