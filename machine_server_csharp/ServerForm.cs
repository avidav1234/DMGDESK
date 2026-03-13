using System;
using System.Drawing;
using System.Windows.Forms;

namespace MachineServer
{
    /// <summary>
    /// Finestra principale del server.
    /// Si minimizza nella taskbar all'avvio.
    /// Menu: Impostazioni per cambiare cartella base e porta.
    /// </summary>
    public class ServerForm : Form
    {
        private ServerConfig _config;
        private SocketServer _server;

        // Controlli UI
        private Label       _lblStato;
        private Label       _lblPorta;
        private Label       _lblPath;
        private RichTextBox _logBox;
        private MenuStrip   _menu;

        public ServerForm()
        {
            _config = ServerConfig.Load();
            InitializeComponent();
            StartServer();

            // Minimizza subito nella taskbar
            this.WindowState = FormWindowState.Minimized;
        }

        // ── Build UI ──────────────────────────────────────────────────────────

        private void InitializeComponent()
        {
            this.Text            = "DMG Machine Server";
            this.Size            = new Size(580, 440);
            this.MinimumSize     = new Size(440, 320);
            this.StartPosition   = FormStartPosition.CenterScreen;
            this.BackColor       = Color.White;
            this.Font            = new Font("Segoe UI", 9f);

            // ── Menu ─────────────────────────────────────────────────────────
            _menu = new MenuStrip();
            _menu.BackColor = Color.FromArgb(21, 101, 192);
            _menu.ForeColor = Color.White;

            ToolStripMenuItem mnuMenu = new ToolStripMenuItem("Menu");
            mnuMenu.ForeColor = Color.White;

            ToolStripMenuItem mnuImpostazioni = new ToolStripMenuItem("⚙  Impostazioni...");
            mnuImpostazioni.Click += new EventHandler(OnImpostazioni);

            ToolStripMenuItem mnuEsci = new ToolStripMenuItem("Esci");
            mnuEsci.Click += new EventHandler(OnEsci);

            mnuMenu.DropDownItems.Add(mnuImpostazioni);
            mnuMenu.DropDownItems.Add(new ToolStripSeparator());
            mnuMenu.DropDownItems.Add(mnuEsci);
            _menu.Items.Add(mnuMenu);
            this.MainMenuStrip = _menu;
            this.Controls.Add(_menu);

            // ── Header ───────────────────────────────────────────────────────
            Panel header = new Panel();
            header.BackColor = Color.FromArgb(21, 101, 192);
            header.Height    = 46;
            header.Dock      = DockStyle.Top;
            header.Padding   = new Padding(0, _menu.Height, 0, 0);

            Label lblTitle = new Label();
            lblTitle.Text      = "DMG Machine Server";
            lblTitle.Font      = new Font("Segoe UI", 13f, FontStyle.Bold);
            lblTitle.ForeColor = Color.White;
            lblTitle.AutoSize  = true;
            lblTitle.Location  = new Point(14, 14 + _menu.Height);
            header.Controls.Add(lblTitle);

            _lblStato = new Label();
            _lblStato.Text      = "⏳ Avvio...";
            _lblStato.Font      = new Font("Segoe UI", 9f);
            _lblStato.ForeColor = Color.FromArgb(144, 202, 249);
            _lblStato.AutoSize  = true;
            _lblStato.Anchor    = AnchorStyles.Right | AnchorStyles.Top;
            _lblStato.Location  = new Point(420, 16 + _menu.Height);
            header.Controls.Add(_lblStato);

            this.Controls.Add(header);

            // ── Info box ─────────────────────────────────────────────────────
            Panel info = new Panel();
            info.BackColor = Color.FromArgb(227, 242, 253);
            info.Height    = 52;
            info.Dock      = DockStyle.Top;
            info.Padding   = new Padding(10, 4, 10, 4);

            _lblPorta = new Label();
            _lblPorta.AutoSize  = true;
            _lblPorta.Location  = new Point(10, 6);
            _lblPorta.Font      = new Font("Segoe UI", 9f);
            info.Controls.Add(_lblPorta);

            _lblPath = new Label();
            _lblPath.AutoSize  = true;
            _lblPath.Location  = new Point(10, 26);
            _lblPath.Font      = new Font("Segoe UI", 9f);
            info.Controls.Add(_lblPath);

            this.Controls.Add(info);

            // ── Log label ────────────────────────────────────────────────────
            Label lblLog = new Label();
            lblLog.Text     = "Log attività:";
            lblLog.Font     = new Font("Segoe UI", 9f, FontStyle.Bold);
            lblLog.AutoSize = true;
            lblLog.Dock     = DockStyle.Top;
            lblLog.Padding  = new Padding(10, 8, 0, 2);
            this.Controls.Add(lblLog);

            // ── Log box ──────────────────────────────────────────────────────
            _logBox = new RichTextBox();
            _logBox.Dock      = DockStyle.Fill;
            _logBox.ReadOnly  = true;
            _logBox.BackColor = Color.FromArgb(250, 250, 250);
            _logBox.Font      = new Font("Courier New", 8f);
            _logBox.ScrollBars = RichTextBoxScrollBars.Vertical;
            this.Controls.Add(_logBox);

            // Padding sotto il menu
            header.Height = 46 + _menu.Height;

            AggiornaCampiInfo();

            this.FormClosing += new FormClosingEventHandler(OnFormClosing);
        }

        // ── Server ────────────────────────────────────────────────────────────

        private void StartServer()
        {
            if (_server != null) _server.Stop();

            _server        = new SocketServer(_config);
            _server.OnLog += new SocketServer.LogHandler(AppendLog);
            _server.Start();

            if (_lblStato != null)
                _lblStato.Text = "🟢 In ascolto :" + _config.Port;
        }

        // ── Log (thread-safe) ─────────────────────────────────────────────────

        private void AppendLog(string msg)
        {
            if (_logBox.InvokeRequired)
            {
                _logBox.Invoke(new MethodInvoker(delegate { AppendLog(msg); }));
                return;
            }

            Color col = Color.FromArgb(51, 51, 51);
            if (msg.Contains("✅"))      col = Color.FromArgb(46, 125, 50);
            else if (msg.Contains("❌")) col = Color.FromArgb(198, 40, 40);
            else if (msg.Contains("🔍") || msg.Contains("🔌") ||
                     msg.Contains("📂") || msg.Contains("📁") ||
                     msg.Contains("⚙"))  col = Color.FromArgb(21, 101, 192);

            _logBox.SelectionStart  = _logBox.TextLength;
            _logBox.SelectionLength = 0;
            _logBox.SelectionColor  = col;
            _logBox.AppendText(msg + "\r\n");
            _logBox.ScrollToCaret();
        }

        // ── Helpers UI ────────────────────────────────────────────────────────

        private void AggiornaCampiInfo()
        {
            if (_lblPorta != null) _lblPorta.Text = "Porta:          " + _config.Port;
            if (_lblPath  != null) _lblPath.Text  = "Cartella base:  " + _config.BasePath;
            if (_lblStato != null) _lblStato.Text = "🟢 In ascolto :" + _config.Port;
        }

        // ── Event handlers ────────────────────────────────────────────────────

        private void OnImpostazioni(object sender, EventArgs e)
        {
            ImpostazioniForm dlg = new ImpostazioniForm(_config.Port, _config.BasePath);
            if (dlg.ShowDialog(this) == DialogResult.OK)
            {
                _config.Port     = dlg.SelectedPort;
                _config.BasePath = dlg.SelectedBasePath;
                _config.Save();
                AggiornaCampiInfo();
                StartServer();
                AppendLog("⚙  Impostazioni aggiornate — porta " +
                          _config.Port + "  |  " + _config.BasePath);
            }
        }

        private void OnEsci(object sender, EventArgs e)
        {
            if (MessageBox.Show(
                    "Chiudendo il server i file non potranno più\n" +
                    "essere inviati dalla postazione operatore.\n\nVuoi chiudere?",
                    "Chiudi server",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Question) == DialogResult.Yes)
            {
                if (_server != null) _server.Stop();
                Application.Exit();
            }
        }

        private void OnFormClosing(object sender, FormClosingEventArgs e)
        {
            if (e.CloseReason == CloseReason.UserClosing)
            {
                // Click sulla X → minimizza invece di chiudere
                e.Cancel      = true;
                this.WindowState = FormWindowState.Minimized;
            }
        }
    }

    // ── Dialog Impostazioni ───────────────────────────────────────────────────

    public class ImpostazioniForm : Form
    {
        public int    SelectedPort     { get; private set; }
        public string SelectedBasePath { get; private set; }

        private TextBox _txtPort;
        private TextBox _txtPath;

        public ImpostazioniForm(int port, string basePath)
        {
            this.Text            = "Impostazioni Server";
            this.Size            = new Size(500, 240);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox     = false;
            this.MinimizeBox     = false;
            this.StartPosition   = FormStartPosition.CenterParent;
            this.Font            = new Font("Segoe UI", 9f);
            this.BackColor       = Color.White;

            // Porta
            Label lblPorta = new Label();
            lblPorta.Text     = "Porta:";
            lblPorta.Font     = new Font("Segoe UI", 9f, FontStyle.Bold);
            lblPorta.Location = new Point(16, 20);
            lblPorta.AutoSize = true;
            this.Controls.Add(lblPorta);

            _txtPort          = new TextBox();
            _txtPort.Text     = port.ToString();
            _txtPort.Location = new Point(120, 18);
            _txtPort.Width    = 70;
            this.Controls.Add(_txtPort);

            // Cartella base
            Label lblPath = new Label();
            lblPath.Text     = "Cartella base:";
            lblPath.Font     = new Font("Segoe UI", 9f, FontStyle.Bold);
            lblPath.Location = new Point(16, 58);
            lblPath.AutoSize = true;
            this.Controls.Add(lblPath);

            _txtPath          = new TextBox();
            _txtPath.Text     = basePath;
            _txtPath.Location = new Point(120, 56);
            _txtPath.Width    = 300;
            this.Controls.Add(_txtPath);

            Button btnSfoglia = new Button();
            btnSfoglia.Text     = "📁";
            btnSfoglia.Location = new Point(428, 54);
            btnSfoglia.Size     = new Size(36, 24);
            btnSfoglia.Click   += new EventHandler(OnSfoglia);
            this.Controls.Add(btnSfoglia);

            // Nota
            Label nota = new Label();
            nota.Text      = "La sottocartella con il nome del progetto viene aggiunta automaticamente.\n" +
                             "Esempio:  [cartella base]\\NOME_PROGETTO\\file.MPF";
            nota.Font      = new Font("Segoe UI", 8f);
            nota.ForeColor = Color.FromArgb(100, 100, 100);
            nota.Location  = new Point(16, 96);
            nota.Size      = new Size(450, 36);
            this.Controls.Add(nota);

            // Bottoni
            Button btnOk = new Button();
            btnOk.Text             = "💾  Salva e riavvia";
            btnOk.Location         = new Point(120, 150);
            btnOk.Size             = new Size(150, 32);
            btnOk.BackColor        = Color.FromArgb(21, 101, 192);
            btnOk.ForeColor        = Color.White;
            btnOk.FlatStyle        = FlatStyle.Flat;
            btnOk.Font             = new Font("Segoe UI", 9f, FontStyle.Bold);
            btnOk.Click           += new EventHandler(OnSalva);
            this.Controls.Add(btnOk);

            Button btnAnnulla = new Button();
            btnAnnulla.Text         = "Annulla";
            btnAnnulla.Location     = new Point(284, 150);
            btnAnnulla.Size         = new Size(90, 32);
            btnAnnulla.DialogResult = DialogResult.Cancel;
            this.Controls.Add(btnAnnulla);
        }

        private void OnSfoglia(object sender, EventArgs e)
        {
            FolderBrowserDialog dlg = new FolderBrowserDialog();
            dlg.Description         = "Seleziona cartella base destinazione";
            dlg.SelectedPath        = _txtPath.Text;
            if (dlg.ShowDialog() == DialogResult.OK)
                _txtPath.Text = dlg.SelectedPath;
        }

        private void OnSalva(object sender, EventArgs e)
        {
            int p;
            if (!int.TryParse(_txtPort.Text.Trim(), out p))
            {
                MessageBox.Show("Porta non valida", "Errore",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            if (string.IsNullOrEmpty(_txtPath.Text.Trim()))
            {
                MessageBox.Show("Inserisci cartella base", "Errore",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            SelectedPort     = p;
            SelectedBasePath = _txtPath.Text.Trim();
            this.DialogResult = DialogResult.OK;
        }
    }
}
