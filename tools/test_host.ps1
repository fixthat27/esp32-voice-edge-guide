$ErrorActionPreference = 'Stop'
# Run from the extracted bundle root with a Python environment activated.
New-Item -ItemType Directory -Force build | Out-Null
gcc -O2 -Wall -Wextra -shared firmware/shared/mfcc.c -o build/mfcc.dll -lm
if ($LASTEXITCODE -ne 0) { throw 'C compilation failed' }
$env:MFCC_LIB = (Resolve-Path build/mfcc.dll).Path
python -m unittest discover -s test -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
