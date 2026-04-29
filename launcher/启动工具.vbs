Set objShell = CreateObject("WScript.Shell")
Set objEnv = objShell.Environment("Process")
objEnv("PYTHONUTF8") = "1"
objShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "D:\python3.13\python.exe main.py", 0, False
