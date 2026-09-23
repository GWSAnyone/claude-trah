@echo off
rem GWS-CLAUDE-WRAPPER - marker: the hook and the service find their wrapper by it,
rem reading the first 512 bytes of the entry point. It must stay near the top.
rem
rem This file is only a shim: the logic lives in claude-wrapper.sh next to it.
rem Windows resolves .EXE before .CMD, so this directory has to come EARLIER in
rem PATH than ~/.local/bin, where the real claude.exe lives.
rem
rem ASCII only on purpose: cmd.exe reads a .cmd in the OEM codepage, and a
rem mangled line here would be a parse error on the path of every launch.
rem
rem The rule from the bash wrapper holds and matters more here: never get in the
rem way of claude starting. No bash, no script, anything unclear - run the real
rem binary directly, without the flag.
setlocal
set "WRAPPER=%~dp0claude-wrapper.sh"
set "REAL=%USERPROFILE%\.local\bin\claude.exe"

if not exist "%WRAPPER%" goto fallback

set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%BASH%" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not exist "%BASH%" for %%B in (bash.exe) do set "BASH=%%~$PATH:B"
if not exist "%BASH%" goto fallback

"%BASH%" "%WRAPPER%" %*
exit /b %ERRORLEVEL%

:fallback
if not exist "%REAL%" (
    echo claude: real binary not found at "%REAL%" 1>&2
    exit /b 127
)
"%REAL%" %*
exit /b %ERRORLEVEL%
