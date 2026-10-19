Option Explicit
Dim shell, fso, home, pythonw, command, folder
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
home = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = ""
For Each folder In Split(shell.ExpandEnvironmentStrings("%PATH%"), ";")
  If fso.FileExists(fso.BuildPath(folder, "pythonw.exe")) Then
    pythonw = fso.BuildPath(folder, "pythonw.exe")
    Exit For
  End If
Next
If pythonw = "" Then
  MsgBox "Khong tim thay pythonw.exe trong PATH.", vbExclamation, "Text Browser"
  WScript.Quit 1
End If
command = """" & pythonw & """ """ & home & "\run_addin.pyw"""
shell.Run command, 0, False
