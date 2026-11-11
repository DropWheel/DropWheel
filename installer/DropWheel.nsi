; Instalador de DropWheel (se compila con makensis; ver installer/build.sh)
Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"

!define APPNAME "DropWheel"
!define APPVER "1.1.0"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\DropWheel"
!define RUNKEY "Software\Microsoft\Windows\CurrentVersion\Run"

Name "${APPNAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\DropWheel"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64
BrandingText "DropWheel ${APPVER}"
ShowInstDetails nevershow
!define MUI_ICON "${BUILDDIR}\dropwheel.ico"
!define MUI_UNICON "${BUILDDIR}\dropwheel.ico"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Instalar DropWheel"
!define MUI_WELCOMEPAGE_TEXT "DropWheel agrega una rueda de conversión a tus archivos: mantén Shift, arrastra un archivo y suéltalo sobre el formato que quieras. Siempre crea una copia y no toca el original.$\r$\n$\r$\nNo necesitas instalar nada más; todo viene incluido."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir DropWheel ahora"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Iniciar DropWheel con Windows"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION SetAutostart
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Function LaunchApp
  SetOutPath "$INSTDIR\app"
  Exec '"$INSTDIR\python\DropWheel.exe" "$INSTDIR\app\DropWheel.pyw"'
FunctionEnd

Function SetAutostart
  WriteRegStr HKCU "${RUNKEY}" "DropWheel" '"$INSTDIR\python\DropWheel.exe" "$INSTDIR\app\DropWheel.pyw"'
FunctionEnd

Section "Instalar"
  ; cerrar una copia que esté corriendo (actualización)
  nsExec::Exec 'taskkill /F /IM DropWheel.exe'
  Sleep 400
  SetOutPath "$INSTDIR"
  File "${BUILDDIR}\dropwheel.ico"
  SetOutPath "$INSTDIR\python"
  File /r "${BUILDDIR}\python\*.*"
  SetOutPath "$INSTDIR\app"
  File /r "${BUILDDIR}\app\*.*"

  SetOutPath "$INSTDIR\app"
  CreateDirectory "$SMPROGRAMS\DropWheel"
  CreateShortcut "$SMPROGRAMS\DropWheel\DropWheel.lnk" "$INSTDIR\python\DropWheel.exe" '"$INSTDIR\app\DropWheel.pyw"' "$INSTDIR\dropwheel.ico" 0
  CreateShortcut "$SMPROGRAMS\DropWheel\Desinstalar DropWheel.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\DropWheel.lnk" "$INSTDIR\python\DropWheel.exe" '"$INSTDIR\app\DropWheel.pyw"' "$INSTDIR\dropwheel.ico" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "DropWheel"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${APPVER}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "David Arenas"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\dropwheel.ico"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
  nsExec::Exec 'taskkill /F /IM DropWheel.exe'
  Sleep 400
  Delete "$SMPROGRAMS\DropWheel\DropWheel.lnk"
  Delete "$SMPROGRAMS\DropWheel\Desinstalar DropWheel.lnk"
  RMDir "$SMPROGRAMS\DropWheel"
  Delete "$DESKTOP\DropWheel.lnk"
  DeleteRegValue HKCU "${RUNKEY}" "DropWheel"
  DeleteRegKey HKCU "${UNINSTKEY}"
  RMDir /r "$INSTDIR"
SectionEnd
