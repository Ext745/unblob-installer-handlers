; Inno Setup fixture: installs the 4 KiB fixture payload as firmware.bin.
; Cut down from the Script Wizard template
; (gist.github.com/m-biernat/45dfe8494916e2d2f4fae408caaea3b1).
#ifndef OutName
  #define OutName "standard"
#endif

[Setup]
AppId=UIH-FIXTURE
AppName=UIH fixture
AppVersion=1.0
DefaultDirName={tmp}\uih-fixture
DisableProgramGroupPage=yes
DisableDirPage=yes
Uninstallable=no
PrivilegesRequired=lowest
OutputDir=out
OutputBaseFilename={#OutName}
Compression=lzma2
SolidCompression=yes
TouchDate=2023-11-14
TouchTime=22:13:20

[Files]
Source: "firmware.bin"; DestDir: "{app}"
