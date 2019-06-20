start /B python zubax-kucher
echo ok
timeout 20
tasklist /fi "windowtitle eq Zubax Kucher"|find ":" > nul
echo %errorlevel%
if errorlevel 1 (
    taskkill /fi "windowtitle eq Zubax Kucher"
    echo No error found
    exit 0
) else (
    echo Error in program
    exit 1
)
