using System;
using System.Data.SQLite;
using System.Drawing;
using System.Windows.Forms;

namespace SupportDesk.forms
{
    /// <summary>Только просмотр. Пишет не эта форма, а вход/выход из программы.</summary>
    public partial class ServerAccessLogForm : Form
    {
        private SQLiteConnection DB;
        private DataGridView grid;
        private Label statusLabel;

        public ServerAccessLogForm()
        {
            InitializeComponent();
            Text = "Журнал";
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            Size = new Size(1000, 560);
            BackColor = Color.FromArgb(24, 28, 36);
            ForeColor = Color.White;
            Font = new Font("Arial", 10);

            Label title = new Label
            {
                Text = "Журнал входа / выхода из программы",
                Font = new Font("Arial", 15, FontStyle.Bold),
                ForeColor = Color.White,
                Location = new Point(20, 12),
                AutoSize = true
            };
            Controls.Add(title);
            title.MouseDown += Drag;

            Button close = MakeButton("Закрыть", 880, 12, 100, 32);
            close.Click += (s, e) => ReturnBack();
            Controls.Add(close);

            statusLabel = new Label
            {
                Text = "Данные пишутся при входе в программу и при выходе из аккаунта.",
                Location = new Point(20, 48),
                Size = new Size(900, 22),
                ForeColor = Color.LightGreen
            };
            Controls.Add(statusLabel);

            grid = new DataGridView
            {
                Location = new Point(20, 80),
                Size = new Size(960, 400),
                ReadOnly = true,
                AllowUserToAddRows = false,
                AllowUserToResizeRows = false,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                MultiSelect = false,
                BackgroundColor = Color.FromArgb(36, 42, 54),
                BorderStyle = BorderStyle.None,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                RowHeadersVisible = false,
                EnableHeadersVisualStyles = false,
                GridColor = Color.FromArgb(60, 70, 85)
            };
            // Текст всегда белый — иначе на тёмном фоне не видно, пока не наведёшь
            grid.DefaultCellStyle.BackColor = Color.FromArgb(36, 42, 54);
            grid.DefaultCellStyle.ForeColor = Color.White;
            grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(0, 116, 228);
            grid.DefaultCellStyle.SelectionForeColor = Color.White;
            grid.DefaultCellStyle.Font = new Font("Arial", 10F);
            grid.AlternatingRowsDefaultCellStyle.BackColor = Color.FromArgb(45, 52, 66);
            grid.AlternatingRowsDefaultCellStyle.ForeColor = Color.White;
            grid.AlternatingRowsDefaultCellStyle.SelectionBackColor = Color.FromArgb(0, 116, 228);
            grid.AlternatingRowsDefaultCellStyle.SelectionForeColor = Color.White;
            grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(0, 116, 228);
            grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.White;
            grid.ColumnHeadersDefaultCellStyle.Font = new Font("Arial", 10F, FontStyle.Bold);
            grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = Color.FromArgb(0, 116, 228);
            grid.ColumnHeadersHeight = 32;
            grid.RowTemplate.Height = 28;

            grid.Columns.Add("id", "ID");
            grid.Columns.Add("visitor", "Кто");
            grid.Columns.Add("enterDate", "Дата входа");
            grid.Columns.Add("enterTime", "Время входа");
            grid.Columns.Add("exitTime", "Время выхода");
            grid.Columns.Add("note", "Что делал");
            grid.Columns["id"].Visible = false;
            Controls.Add(grid);

            Button refresh = MakeButton("Обновить", 20, 500, 140, 36);
            refresh.Click += (s, e) => LoadRows();
            Button del = MakeButton("Удалить (ADMIN)", 170, 500, 160, 36);
            del.Click += async (s, e) => await DeleteRow();
            Controls.Add(refresh);
            Controls.Add(del);

            Load += async (s, e) =>
            {
                try
                {
                    DB = new SQLiteConnection(Database.connectionString);
                    await DB.OpenAsync();
                    await NewModulesDb.EnsureAsync(DB);
                    LoadRows();
                    if (grid.Rows.Count == 0)
                        statusLabel.Text = "Пока пусто. Выйди и зайди в программу заново — должна появиться строка.";
                    else
                        statusLabel.Text = "Записей: " + grid.Rows.Count + ". Зелёные — ещё в системе (нет времени выхода).";
                }
                catch (Exception ex)
                {
                    statusLabel.ForeColor = Color.OrangeRed;
                    statusLabel.Text = ex.Message;
                    MessageBox.Show(ex.Message, "Журнал");
                }
            };
            MouseDown += Drag;
        }

        private Button MakeButton(string text, int x, int y, int w, int h)
        {
            return new Button
            {
                Text = text, Location = new Point(x, y), Size = new Size(w, h),
                FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(0, 116, 228), ForeColor = Color.White
            };
        }

        private async void LoadRows()
        {
            if (DB == null) return;
            grid.Rows.Clear();
            using (SQLiteCommand command = new SQLiteCommand(
                "SELECT ID, visitor, enterDate, enterTime, exitTime, note FROM ServerRoomVisits ORDER BY ID DESC", DB))
            {
                SQLiteDataReader reader = null;
                try
                {
                    reader = (SQLiteDataReader)await command.ExecuteReaderAsync();
                    while (await reader.ReadAsync())
                    {
                        string exitT = Convert.ToString(reader["exitTime"]);
                        int row = grid.Rows.Add(
                            reader["ID"].ToString(),
                            reader["visitor"].ToString(),
                            reader["enterDate"].ToString(),
                            reader["enterTime"].ToString(),
                            exitT,
                            Convert.ToString(reader["note"]));
                        if (string.IsNullOrEmpty(exitT))
                        {
                            grid.Rows[row].DefaultCellStyle.BackColor = Color.FromArgb(40, 80, 40);
                            grid.Rows[row].DefaultCellStyle.ForeColor = Color.White;
                        }
                        else
                        {
                            grid.Rows[row].DefaultCellStyle.ForeColor = Color.White;
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Журнал");
                }
                finally { reader?.Close(); }
            }
        }

        private async System.Threading.Tasks.Task DeleteRow()
        {
            if (DataUsers.GroupUser != "ADMIN") { MessageBoxUI.Show("Только ADMIN.", "Журнал", "Error"); return; }
            if (grid.SelectedRows.Count == 0) return;
            string id = grid.SelectedRows[0].Cells["id"].Value.ToString();
            using (SQLiteCommand command = new SQLiteCommand("DELETE FROM ServerRoomVisits WHERE ID=@id", DB))
            {
                command.Parameters.AddWithValue("id", id);
                await command.ExecuteNonQueryAsync();
            }
            LoadRows();
        }

        private void ReturnBack()
        {
            Form next = DataUsers.GroupUser == "ADMIN" ? (Form)new MainAdminForm() : new MainWorkerForm();
            next.Show();
            next.FormClosed += (s, e) => Close();
            Hide();
        }

        private void Drag(object sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                Capture = false;
                Message m = Message.Create(Handle, 0xA1, new IntPtr(2), IntPtr.Zero);
                WndProc(ref m);
            }
        }
    }
}
