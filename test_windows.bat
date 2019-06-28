start /B python zubax-kucher
timeout 20
tasklist /fi "windowtitle eq Zubax Kucher"|find ":" > nul
if errorlevel 1 (
    taskkill /fi "windowtitle eq Zubax Kucher"
    exit 0
) else (
    echo Error found
    exit 1
)
