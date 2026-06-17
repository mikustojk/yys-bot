using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace YysBotLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
    }

    internal sealed class LauncherForm : Form
    {
        private readonly string appDir;
        private readonly Panel countPanel;
        private readonly Label countLabel;
        private readonly LogPanel logBox;
        private readonly NotePanel noteBox;
        private readonly NumericUpDown runCount;
        private readonly Button k28Button;
        private readonly Button shuaButton;
        private readonly Button ignoreSizeButton;
        private readonly Button captureButton;
        private readonly Button stopButton;
        private Process currentProcess;
        private Image backgroundImage;

        public LauncherForm()
        {
            appDir = AppDomain.CurrentDomain.BaseDirectory;
            Text = "YYS Bot Launcher";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            Opacity = 1.0;
            Font = new Font("Microsoft YaHei UI", 10F, FontStyle.Regular, GraphicsUnit.Point);
            DoubleBuffered = true;

            LoadBackgroundAndSize();

            countPanel = new Panel();
            countPanel.BackColor = Color.FromArgb(204, 245, 245, 245);
            countPanel.BorderStyle = BorderStyle.FixedSingle;
            Controls.Add(countPanel);

            countLabel = new Label();
            countLabel.Text = "运行次数：";
            countLabel.AutoSize = false;
            countLabel.BackColor = Color.Transparent;
            countLabel.ForeColor = Color.Black;
            countLabel.Font = new Font("Microsoft YaHei UI", 20F, FontStyle.Bold, GraphicsUnit.Point);
            countLabel.TextAlign = ContentAlignment.MiddleRight;
            countPanel.Controls.Add(countLabel);

            runCount = new NumericUpDown();
            runCount.Minimum = 1;
            runCount.Maximum = 9999;
            runCount.Value = 1;
            runCount.Font = new Font("Microsoft YaHei UI", 20F, FontStyle.Bold, GraphicsUnit.Point);
            countPanel.Controls.Add(runCount);

            k28Button = CreateButton("困难28");
            k28Button.Text = "困难28";
            k28Button.Click += delegate { StartScript("maa_lite_k28.py"); };
            Controls.Add(k28Button);

            shuaButton = CreateButton("挑战");
            shuaButton.Text = "刷挑战";
            shuaButton.Click += delegate { StartScript("忽略尺寸刷.py"); };
            Controls.Add(shuaButton);

            ignoreSizeButton = CreateButton("忽略尺寸刷");
            ignoreSizeButton.Click += delegate { StartScript("忽略尺寸刷.py"); };
            ignoreSizeButton.Visible = false;
            Controls.Add(ignoreSizeButton);

            captureButton = CreateButton("自适应K28");
            captureButton.Click += delegate { StartScript("maa_lite_k28.py"); };
            captureButton.Visible = false;
            Controls.Add(captureButton);

            stopButton = CreateButton("停止运行");
            stopButton.Text = "停止运行";
            stopButton.Enabled = false;
            stopButton.Click += delegate { StopCurrentProcess(); };
            Controls.Add(stopButton);

            logBox = new LogPanel();
            logBox.BackColor = Color.FromArgb(175, 10, 14, 22);
            logBox.ForeColor = Color.White;
            logBox.Font = new Font("Consolas", 13F, FontStyle.Bold, GraphicsUnit.Point);
            Controls.Add(logBox);

            noteBox = new NotePanel();
            noteBox.BackColor = Color.FromArgb(180, 10, 14, 22);
            noteBox.ForeColor = Color.FromArgb(255, 248, 232);
            noteBox.Font = new Font("Microsoft YaHei UI", 13F, FontStyle.Bold, GraphicsUnit.Point);
            noteBox.TitleFont = new Font("Microsoft YaHei UI", 18F, FontStyle.Bold, GraphicsUnit.Point);
            noteBox.Text = "1. 配环境：首次使用先运行 setup_env.ps1。看到 Environment ready 后，再打开 script.exe。\n\n2. 自适应脚本模板用 capture_maa_template.py 截图，保存到 images/maa。\n\n3. 先填写好运行次数，再点击按钮运行。";
            Controls.Add(noteBox);

            LayoutContentPanels();

            AppendLog("Ready.");
            AppendLog("Working directory: " + appDir);
            string python = FindPython();
            AppendLog(python == null ? "No usable Python found. It will be checked again when running." : "Python detected: " + python);
            if (python != null && !HasBotDependencies(python))
            {
                AppendLog("Warning: detected Python is missing cv2/numpy/win32gui. Scripts may fail until dependencies are installed.");
            }
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            LayoutContentPanels();
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            if (backgroundImage == null)
            {
                base.OnPaintBackground(e);
                return;
            }

            e.Graphics.DrawImage(backgroundImage, ClientRectangle);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            StopCurrentProcess();
            if (backgroundImage != null)
            {
                backgroundImage.Dispose();
            }
            base.OnFormClosing(e);
        }

        private Button CreateButton(string text)
        {
            Button button = new Button();
            button.Text = text;
            button.Font = new Font("Microsoft YaHei UI", 20F, FontStyle.Bold, GraphicsUnit.Point);
            button.FlatStyle = FlatStyle.Flat;
            button.BackColor = Color.FromArgb(204, 245, 245, 245);
            button.ForeColor = Color.Black;
            button.FlatAppearance.BorderColor = Color.FromArgb(204, 190, 190, 190);
            button.FlatAppearance.MouseOverBackColor = Color.FromArgb(204, 255, 255, 255);
            button.FlatAppearance.MouseDownBackColor = Color.FromArgb(204, 220, 220, 220);
            return button;
        }

        private void LayoutContentPanels()
        {
            if (countPanel == null || countLabel == null || runCount == null || k28Button == null || shuaButton == null || ignoreSizeButton == null || captureButton == null || stopButton == null || logBox == null || noteBox == null || ClientSize.Width <= 0 || ClientSize.Height <= 0)
            {
                return;
            }

            int left = 24;
            int right = 24;
            int gap = 16;
            int topControlsHeight = ClientSize.Width < 1180 ? 64 : 80;
            int buttonGap = ClientSize.Width < 1180 ? 14 : 24;
            int countPanelWidth = Math.Max(350, Math.Min(430, (int)(ClientSize.Width * 0.22)));
            int countPanelX = ClientSize.Width - right - countPanelWidth;
            int top = Math.Max(135, (int)(ClientSize.Height * 0.13));
            int topControlsY = Math.Max(12, (top - topControlsHeight) / 2);
            int logoClearLeft = ClientSize.Width < 1180 ? Math.Max(left, (int)(ClientSize.Width * 0.12)) : Math.Max(300, (int)(ClientSize.Width * 0.155));
            int availableForButtons = Math.Max(600, countPanelX - logoClearLeft - buttonGap);
            int buttonWidth = Math.Max(170, Math.Min(260, (availableForButtons - buttonGap * 2) / 3));

            int buttonX = logoClearLeft;
            k28Button.Location = new Point(buttonX, topControlsY);
            k28Button.Size = new Size(buttonWidth, topControlsHeight);

            buttonX += buttonWidth + buttonGap;
            shuaButton.Location = new Point(buttonX, topControlsY);
            shuaButton.Size = new Size(buttonWidth, topControlsHeight);

            buttonX += buttonWidth + buttonGap;
            stopButton.Location = new Point(buttonX, topControlsY);
            stopButton.Size = new Size(buttonWidth, topControlsHeight);

            countPanel.Location = new Point(countPanelX, topControlsY);
            countPanel.Size = new Size(countPanelWidth, topControlsHeight);
            int countInputWidth = 110;
            int countLabelWidth = TextRenderer.MeasureText(countLabel.Text, countLabel.Font).Width + 8;
            int countContentWidth = countLabelWidth + countInputWidth + 18;
            int countStartX = Math.Max(16, (countPanelWidth - countContentWidth) / 2);

            countLabel.Location = new Point(countStartX, 0);
            countLabel.Size = new Size(countLabelWidth, topControlsHeight);
            runCount.Location = new Point(countStartX + countLabelWidth + 18, (topControlsHeight - 42) / 2);
            runCount.Size = new Size(countInputWidth, 42);

            int bottom = 30;
            int notesWidth = Math.Max(420, Math.Min(600, (int)(ClientSize.Width * 0.30)));
            int height = Math.Max(180, ClientSize.Height - top - bottom);
            int logWidth = Math.Max(320, ClientSize.Width - left - right - gap - notesWidth);

            logBox.Location = new Point(left, top);
            logBox.Size = new Size(logWidth, height);

            noteBox.Location = new Point(left + logWidth + gap, top);
            noteBox.Size = new Size(notesWidth, height);
        }

        private void LoadBackgroundAndSize()
        {
            string backgroundPath = Path.Combine(appDir, "background.jpg");
            Size targetSize = new Size(960, 540);

            if (File.Exists(backgroundPath))
            {
                backgroundImage = Image.FromFile(backgroundPath);
                BackgroundImage = backgroundImage;
                BackgroundImageLayout = ImageLayout.Stretch;
                Rectangle workArea = Screen.PrimaryScreen.WorkingArea;
                double scale = Math.Min((workArea.Width * 0.9) / backgroundImage.Width, (workArea.Height * 0.9) / backgroundImage.Height);
                if (scale > 1.0)
                {
                    scale = 1.0;
                }
                targetSize = new Size(Math.Max(760, (int)(backgroundImage.Width * scale)), Math.Max(430, (int)(backgroundImage.Height * scale)));
            }

            ClientSize = targetSize;
        }

        private void StartScript(string scriptName)
        {
            if (currentProcess != null && !currentProcess.HasExited)
            {
                AppendLog("A script is already running. Stop it or wait until it exits.");
                return;
            }

            string scriptPath = Path.Combine(appDir, scriptName);
            if (!File.Exists(scriptPath))
            {
                AppendLog("Script not found: " + scriptPath);
                return;
            }

            string python = FindPython();
            if (python == null)
            {
                AppendLog("No usable Python found. Set YYS_BOT_PYTHON to python.exe if needed.");
                return;
            }
            if (!HasBotDependencies(python))
            {
                AppendLog("Warning: Python is missing cv2/numpy/win32gui. Starting anyway so the script error is visible here.");
            }

            try
            {
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = python;
                info.Arguments = "-u \"" + scriptPath + "\" " + runCount.Value.ToString();
                info.WorkingDirectory = appDir;
                info.UseShellExecute = false;
                info.RedirectStandardInput = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                info.CreateNoWindow = true;
                info.StandardOutputEncoding = Encoding.UTF8;
                info.StandardErrorEncoding = Encoding.UTF8;
                info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                info.EnvironmentVariables["PYTHONUTF8"] = "1";
                info.EnvironmentVariables["YYS_BOT_TIMES"] = runCount.Value.ToString();

                currentProcess = new Process();
                currentProcess.StartInfo = info;
                currentProcess.EnableRaisingEvents = true;
                currentProcess.OutputDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) AppendLog(args.Data); };
                currentProcess.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) AppendLog("[ERROR] " + args.Data); };
                currentProcess.Exited += delegate
                {
                    int exitCode = currentProcess.ExitCode;
                    BeginInvoke(new Action(delegate
                    {
                        AppendLog(scriptName + " exited with code: " + exitCode);
                        SetRunningState(false);
                    }));
                };

                AppendLog("Starting " + scriptName + ", times: " + runCount.Value);
                currentProcess.Start();
                currentProcess.BeginOutputReadLine();
                currentProcess.BeginErrorReadLine();
                SetRunningState(true);
            }
            catch (Exception ex)
            {
                AppendLog("Start failed: " + ex.Message);
                SetRunningState(false);
            }
        }

        private void StartCapture1010()
        {
            if (currentProcess != null && !currentProcess.HasExited)
            {
                AppendLog("A script is already running. Stop it or wait until it exits.");
                return;
            }

            string scriptPath = Path.Combine(appDir, "capture_1010.py");
            if (!File.Exists(scriptPath))
            {
                AppendLog("Capture tool not found: " + scriptPath);
                return;
            }

            string python = FindPython();
            if (python == null)
            {
                AppendLog("No usable Python found. Set YYS_BOT_PYTHON to python.exe if needed.");
                return;
            }
            if (!HasBotDependencies(python))
            {
                AppendLog("Warning: Python is missing cv2/numpy/win32gui. Capture may fail until dependencies are installed.");
            }

            try
            {
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = python;
                info.Arguments = "-u \"" + scriptPath + "\"";
                info.WorkingDirectory = appDir;
                info.UseShellExecute = false;
                info.RedirectStandardInput = true;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                info.CreateNoWindow = true;
                info.StandardOutputEncoding = Encoding.UTF8;
                info.StandardErrorEncoding = Encoding.UTF8;
                info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                info.EnvironmentVariables["PYTHONUTF8"] = "1";

                currentProcess = new Process();
                currentProcess.StartInfo = info;
                currentProcess.EnableRaisingEvents = true;
                currentProcess.OutputDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) AppendLog(args.Data); };
                currentProcess.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) AppendLog("[ERROR] " + args.Data); };
                currentProcess.Exited += delegate
                {
                    int exitCode = currentProcess.ExitCode;
                    BeginInvoke(new Action(delegate
                    {
                        AppendLog("capture_1010.py exited with code: " + exitCode);
                        SetRunningState(false);
                    }));
                };

                AppendLog("Starting capture_1010.py...");
                currentProcess.Start();
                currentProcess.BeginOutputReadLine();
                currentProcess.BeginErrorReadLine();
                SetRunningState(true);
            }
            catch (Exception ex)
            {
                AppendLog("Capture failed: " + ex.Message);
                SetRunningState(false);
            }
        }

        private void StopCurrentProcess()
        {
            try
            {
                if (currentProcess != null && !currentProcess.HasExited)
                {
                    AppendLog("Stopping current script...");
                    currentProcess.Kill();
                    currentProcess.WaitForExit(2000);
                }
            }
            catch (Exception ex)
            {
                AppendLog("Stop failed: " + ex.Message);
            }
            finally
            {
                SetRunningState(false);
            }
        }

        private void SetRunningState(bool running)
        {
            k28Button.Enabled = !running;
            shuaButton.Enabled = !running;
            ignoreSizeButton.Enabled = !running;
            captureButton.Enabled = !running;
            runCount.Enabled = !running;
            stopButton.Enabled = running;
        }

        private void AppendLog(string message)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(AppendLog), message);
                return;
            }

            logBox.AppendLine(DateTime.Now.ToString("HH:mm:ss") + "  " + message);
        }

        private string FindPython()
        {
            string configured = Environment.GetEnvironmentVariable("YYS_BOT_PYTHON");
            if (IsUsablePython(configured))
            {
                return configured;
            }

            string[] candidates = GetPythonCandidates();

            foreach (string candidate in candidates)
            {
                if (IsUsablePython(candidate) && HasBotDependencies(candidate))
                {
                    return candidate;
                }
            }

            foreach (string candidate in candidates)
            {
                if (IsUsablePython(candidate))
                {
                    return candidate;
                }
            }

            return null;
        }

        private string[] GetPythonCandidates()
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            System.Collections.Generic.List<string> candidates = new System.Collections.Generic.List<string>();
            candidates.Add(Path.Combine(appDir, ".venv", "Scripts", "python.exe"));
            candidates.Add(Path.Combine(appDir, "python.exe"));
            candidates.Add(Path.Combine(localAppData, "Programs", "Python", "Python313", "python.exe"));
            candidates.Add(Path.Combine(localAppData, "Programs", "Python", "Python314", "python.exe"));
            candidates.Add(Path.Combine(localAppData, "Programs", "Python", "Python312", "python.exe"));
            candidates.Add(Path.Combine(localAppData, "Programs", "Python", "Python311", "python.exe"));
            candidates.Add(Path.Combine(localAppData, "Programs", "Python", "Python36", "python.exe"));

            string pathValue = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string dir in pathValue.Split(Path.PathSeparator))
            {
                try
                {
                    candidates.Add(Path.Combine(dir.Trim(), "python.exe"));
                }
                catch
                {
                }
            }

            return candidates.ToArray();
        }

        private bool IsUsablePython(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return false;
            }

            try
            {
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = path;
                info.Arguments = "-c \"import sys; print(sys.version_info[0])\"";
                info.UseShellExecute = false;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                info.CreateNoWindow = true;

                using (Process process = Process.Start(info))
                {
                    if (process == null)
                    {
                        return false;
                    }
                    if (!process.WaitForExit(3000))
                    {
                        process.Kill();
                        return false;
                    }
                    return process.ExitCode == 0;
                }
            }
            catch
            {
                return false;
            }
        }

        private bool HasBotDependencies(string path)
        {
            if (!IsUsablePython(path))
            {
                return false;
            }

            try
            {
                ProcessStartInfo info = new ProcessStartInfo();
                info.FileName = path;
                info.Arguments = "-c \"import cv2, numpy, win32gui\"";
                info.UseShellExecute = false;
                info.RedirectStandardOutput = true;
                info.RedirectStandardError = true;
                info.CreateNoWindow = true;

                using (Process process = Process.Start(info))
                {
                    if (process == null)
                    {
                        return false;
                    }
                    if (!process.WaitForExit(5000))
                    {
                        process.Kill();
                        return false;
                    }
                    return process.ExitCode == 0;
                }
            }
            catch
            {
                return false;
            }
        }
    }

    internal sealed class LogPanel : Control
    {
        private readonly System.Collections.Generic.List<string> lines = new System.Collections.Generic.List<string>();
        private const int MaxLines = 1000;

        public LogPanel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
        }

        public void AppendLine(string line)
        {
            lines.Add(line);
            if (lines.Count > MaxLines)
            {
                lines.RemoveRange(0, lines.Count - MaxLines);
            }
            Invalidate();
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            if (Parent == null)
            {
                base.OnPaintBackground(e);
                return;
            }

            GraphicsStateHelper.PaintParentBackground(this, e.Graphics);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            using (SolidBrush brush = new SolidBrush(BackColor))
            {
                e.Graphics.FillRectangle(brush, ClientRectangle);
            }

            using (Pen border = new Pen(Color.FromArgb(170, 220, 220, 220)))
            {
                e.Graphics.DrawRectangle(border, 0, 0, Width - 1, Height - 1);
            }

            Rectangle textRect = new Rectangle(10, 8, Math.Max(1, Width - 20), Math.Max(1, Height - 16));
            int lineHeight = TextRenderer.MeasureText("Ag", Font).Height;
            int visibleLines = Math.Max(1, textRect.Height / lineHeight);
            int start = Math.Max(0, lines.Count - visibleLines);
            int y = textRect.Top;

            for (int i = start; i < lines.Count; i++)
            {
                Rectangle lineRect = new Rectangle(textRect.Left, y, textRect.Width, lineHeight);
                Rectangle shadowRect = new Rectangle(lineRect.Left + 1, lineRect.Top + 1, lineRect.Width, lineRect.Height);
                TextRenderer.DrawText(e.Graphics, lines[i], Font, shadowRect, Color.Black, TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis);
                TextRenderer.DrawText(e.Graphics, lines[i], Font, lineRect, ForeColor, TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis);
                y += lineHeight;
            }
        }
    }

    internal sealed class NotePanel : Control
    {
        public Font TitleFont { get; set; }

        public NotePanel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            if (Parent == null)
            {
                base.OnPaintBackground(e);
                return;
            }

            GraphicsStateHelper.PaintParentBackground(this, e.Graphics);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            using (SolidBrush brush = new SolidBrush(BackColor))
            {
                e.Graphics.FillRectangle(brush, ClientRectangle);
            }

            using (Pen border = new Pen(Color.FromArgb(230, 255, 194, 55), 3F))
            {
                e.Graphics.DrawRectangle(border, 1, 1, Width - 3, Height - 3);
            }

            int padding = 18;
            Rectangle titleRect = new Rectangle(padding, padding, Math.Max(1, Width - padding * 2), 36);
            Rectangle titleShadow = new Rectangle(titleRect.Left + 2, titleRect.Top + 2, titleRect.Width, titleRect.Height);
            TextRenderer.DrawText(e.Graphics, "注意事项", TitleFont ?? Font, titleShadow, Color.Black, TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis);
            TextRenderer.DrawText(e.Graphics, "注意事项", TitleFont ?? Font, titleRect, Color.FromArgb(255, 255, 229, 150), TextFormatFlags.NoPrefix | TextFormatFlags.EndEllipsis);

            Rectangle bodyRect = new Rectangle(padding, padding + 52, Math.Max(1, Width - padding * 2), Math.Max(1, Height - padding * 2 - 52));
            Rectangle bodyShadow = new Rectangle(bodyRect.Left + 1, bodyRect.Top + 1, bodyRect.Width, bodyRect.Height);
            TextRenderer.DrawText(e.Graphics, Text, Font, bodyShadow, Color.Black, TextFormatFlags.NoPrefix | TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl);
            TextRenderer.DrawText(e.Graphics, Text, Font, bodyRect, ForeColor, TextFormatFlags.NoPrefix | TextFormatFlags.WordBreak | TextFormatFlags.TextBoxControl);
        }
    }

    internal static class GraphicsStateHelper
    {
        public static void PaintParentBackground(Control child, Graphics graphics)
        {
            Image image = child.Parent.BackgroundImage;
            if (image != null && child.Parent.ClientSize.Width > 0 && child.Parent.ClientSize.Height > 0)
            {
                RectangleF source = new RectangleF(
                    child.Left * image.Width / (float)child.Parent.ClientSize.Width,
                    child.Top * image.Height / (float)child.Parent.ClientSize.Height,
                    child.Width * image.Width / (float)child.Parent.ClientSize.Width,
                    child.Height * image.Height / (float)child.Parent.ClientSize.Height);
                graphics.DrawImage(image, child.ClientRectangle, source, GraphicsUnit.Pixel);
                return;
            }

            using (SolidBrush brush = new SolidBrush(child.Parent.BackColor))
            {
                graphics.FillRectangle(brush, child.ClientRectangle);
            }
        }
    }
}
