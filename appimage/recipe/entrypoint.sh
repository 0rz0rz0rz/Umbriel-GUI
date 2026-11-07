# Run only the bundled interpreter and packages: ignore user site-packages and any
# PYTHON* variables from the host that could shadow the bundled PySide6/tomlkit.
unset PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE
export PYTHONNOUSERSITE=1
export PYTHONPATH="$APPDIR"

exec "{{ python-executable }}" -s -m umbriel_config_gui "$@"
