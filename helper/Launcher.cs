using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

class Launcher {
    static void Pump(Stream source, Stream destination) {
        byte[] buffer = new byte[8192];
        int count;
        while ((count = source.Read(buffer, 0, buffer.Length)) > 0) {
            destination.Write(buffer, 0, count);
            destination.Flush();
        }
    }
    static int Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = File.ReadAllText(Path.Combine(root, "python-path.txt")).Trim();
            // Chrome supplies only the origin and parent-window argument. Validate before quoting.
            foreach (string arg in args) {
                if (arg.IndexOf('"') >= 0 || arg.IndexOf('\n') >= 0 || arg.IndexOf('\r') >= 0) return 2;
            }
            string arguments = "-u \"" + Path.Combine(root, "host.py") + "\"";
            foreach (string arg in args) arguments += " \"" + arg + "\"";
            var info = new ProcessStartInfo(python, arguments);
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardInput = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            using (Process child = Process.Start(info)) {
                var input = new Thread(() => {
                    try { Pump(Console.OpenStandardInput(), child.StandardInput.BaseStream); }
                    catch (IOException) { }
                    finally { try { child.StandardInput.Close(); } catch { } }
                });
                input.IsBackground = true;
                input.Start();
                var errors = new Thread(() => {
                    try { Pump(child.StandardError.BaseStream, Console.OpenStandardError()); } catch (IOException) { }
                });
                errors.IsBackground = true;
                errors.Start();
                Pump(child.StandardOutput.BaseStream, Console.OpenStandardOutput());
                child.WaitForExit();
                return child.ExitCode;
            }
        } catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
