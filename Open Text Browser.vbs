Option Explicit
Dim shell, fso, home, pythonw, command, folder, workbook, request, ready
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
home = fso.GetParentFolderName(WScript.ScriptFullName)
workbook = fso.BuildPath(home, "Text Browser.xlsx")
If Not fso.FileExists(workbook) Then
  MsgBox "Khong tim thay Text Browser.xlsx", vbExclamation, "Text Browser"
  WScript.Quit 1
End If
ready = False
On Error Resume Next
Set request = CreateObject("MSXML2.ServerXMLHTTP.6.0")
request.setTimeouts 800, 800, 800, 800
request.open "GET", "https://localhost:3010/api/health", False
request.send
If Err.Number = 0 Then ready = (request.Status = 200)
Err.Clear
On Error GoTo 0
If Not ready Then
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
  command = """" & pythonw & """ """ & home & "\run_addin.pyw" & """"
  shell.Run command, 0, False
  WScript.Sleep 1300
End If
If shell.AppActivate("Text Browser.xlsx - Excel") Then
  WScript.Quit 0
End If
shell.Run """" & workbook & """", 1, False
