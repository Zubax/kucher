start python zubax-kucher
echo ok
timeout 15
tasklist /fi "windowtitle eq Zubax Kucher"|find ":" > nul
echo %errorlevel%
if errorlevel 1 (
    taskkill /fi "windowtitle eq Zubax Kucher" 
    exit 0
) else (
    exit 1
)
