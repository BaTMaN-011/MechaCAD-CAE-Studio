Option Explicit
Dim shell, fso, folder, pythonw, script
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = folder & "\.venv\Scripts\pythonw.exe"
script = folder & "\main.pyw"
If Not fso.FileExists(pythonw) Then
    MsgBox "Run setup_windows.bat once before launching the application.", vbInformation, "MechaCAD & CAE Studio"
    WScript.Quit 1
End If
shell.CurrentDirectory = folder
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34), 0, False
