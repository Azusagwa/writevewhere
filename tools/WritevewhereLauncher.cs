using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class WritevewhereLauncher
{
    private static int Main()
    {
        string appDir = AppDomain.CurrentDomain.BaseDirectory;
        string appPy = Path.Combine(appDir, "app.py");
        string pythonw = @"C:\Users\zichuanyan\anaconda3\pythonw.exe";
        string python = @"C:\Users\zichuanyan\anaconda3\python.exe";

        if (!File.Exists(appPy))
        {
            MessageBox.Show(
                "Cannot find app.py next to Writevewhere.exe.",
                "Writevewhere",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }

        string interpreter = File.Exists(pythonw) ? pythonw : python;
        if (!File.Exists(interpreter))
        {
            MessageBox.Show(
                "Cannot find Anaconda Python. Expected: " + python,
                "Writevewhere",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = interpreter,
            Arguments = "\"" + appPy + "\"",
            WorkingDirectory = appDir,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        Process.Start(startInfo);
        return 0;
    }
}
