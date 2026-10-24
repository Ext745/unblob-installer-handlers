; NSIS fixture: installs the 4 KiB fixture payload as firmware.bin.
Unicode true
SetCompressor /SOLID lzma
Name "UIH fixture"
OutFile "standard.exe"
InstallDir "$TEMP\uih-fixture"
RequestExecutionLevel user
Section
  SetOutPath "$INSTDIR"
  File "firmware.bin"
SectionEnd
