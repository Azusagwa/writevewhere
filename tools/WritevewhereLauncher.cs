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

        // Try venv Python first (relative to the exe directory)
        string venvDir = Path.Combine(appDir, ".venv", "Scripts");
        string pythonw = Path.Combine(venvDir, "pythonw.exe");
        string python = Path.Combine(venvDir, "python.exe");

        string interpreter;
        if (File.Exists(pythonw))
            interpreter = pythonw;
        else if (File.Exists(python))
            interpreter = python;
        else
        {
            MessageBox.Show(
                "Cannot find Python in virtual environment.\n" +
                "Expected: " + pythonw + "\n" +
                "Please create a .venv and install dependencies.",
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
