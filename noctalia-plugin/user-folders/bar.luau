function update()
  barWidget.setGlyph("settings")
  barWidget.setText("Umbriel-GUI")
  barWidget.setTooltip("Open Umbriel-GUI settings")
end

function onClick()
  noctalia.togglePanel("umbriel-settings/user-folders:folders")
end

update()
