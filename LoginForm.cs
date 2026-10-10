using SupportDesk.forms;
using System;
using System.Data;
using System.Data.SQLite;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace SupportDesk
{
    public partial class LoginForm : Form
    {
        #region Настройки формы
        public const int WM_NCLBUTTONDOWN = 0xA1;
        public const int HT_CAPTION = 0x2;
        [DllImportAttribute("user32.dll")]
        public static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);
        [DllImportAttribute("user32.dll")]
        public static extern bool ReleaseCapture();
        #endregion
        #region Локальные переменные
        private SQLiteConnection DB;
        private readonly DateTime thisDay = DateTime.Now;
        private readonly string path = Path.GetTempPath();
        private readonly string directory = RememberLogin.directoryName;
        private readonly string nameFileRemember = RememberLogin.fileName;
        private int attemptLogin = 3;
        [Obsolete]
        private readonly Form fbot = new TelegramForm();
        #endregion
        [Obsolete]
        public LoginForm()
        {
            InitializeComponent();
            CheckRemeber();
        }

        [Obsolete]
        private async void LoginForm_Load(object sender, EventArgs e)
        {
            RootAccess.CheckRunApp = true;
            DB = new SQLiteConnection(Database.connectionString);
            await DB.OpenAsync();
            fbot.Show();
        }
        #region Регистрация
        [Obsolete]
        private void ButtonRegUser_Click(object sender, EventArgs e)
        {
            Form fReg = new RegisterForm();
            fReg.Show();
            fReg.FormClosed += new FormClosedEventHandler(Form_FormClosed);
            Hide();
        }
        #endregion
        #region Управление паролем (Глазик)
        private void ExpUIButtonIconCheckUnlock_Click(object sender, EventArgs e)
        {
            TextBoxPassword.UseSystemPasswordChar = true;
            expUIButtonIconCheckUnlock.Visible = false;
            expUIButtonIconCheckLock.Visible = true;
        }
        private void ExpUIButtonIconCheckLock_Click(object sender, EventArgs e)
        {
            TextBoxPassword.UseSystemPasswordChar = false;
            expUIButtonIconCheckUnlock.Visible = true;
            expUIButtonIconCheckLock.Visible = false;
        }
        #endregion
        #region Выход
        private void ButtonExit_Click(object sender, EventArgs e)
        {
            Close();
        }

        private void Form_FormClosed(object sender, FormClosedEventArgs e)
        {
            Close();
        }
        #endregion
        #region Забыли пароль
        private void LabelForgotPassword_Click(object sender, EventArgs e)
        {
            if (DataRequests.IsOpen)
            {
                return;
            }

            Form fForgotPass = new ForgotPasswordForm();
            fForgotPass.Show();
            DataRequests.IsOpen = true;
        }
        #endregion
        #region Сертификат безопасности
        private void CheckValidatePassword()
        {
            string checkPass = DataUsers.Pass.ToLower();
            foreach (string text in CertificateSecurity.noPasswords)
            {
                if (Regex.IsMatch(checkPass, $"\\b{text}\\b"))
                {
                    MessageBoxUI.Show($"{CertificateSecurity.textError}", $"{CertificateSecurity.textHeadError}", "Error");
                }
            }
        }
        #endregion
        #region Запомнить меня
        private void CheckRemeber()
        {
            string lines = File.ReadAllText(path + directory + nameFileRemember);
            if (lines != "")
            {
                string[] adv = Convert.ToString(lines).Split(':');
                TextBoxLogin.Text = adv[0];
                TextBoxPassword.Text = adv[1];
            }
        }
        private void CheckRemember_CheckedChanged(object sender, EventArgs e)
        {
            if (CheckRemember.Checked)
            {
                string login = TextBoxLogin.Text;
                string password = TextBoxPassword.Text;
                string remember = login + ":" + password;
                File.WriteAllText(path + directory + nameFileRemember, $"{remember}");
            }
        }
        #endregion
        #region Управление формой
        private void FormControl(object sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                _ = ReleaseCapture();
                _ = SendMessage(Handle, WM_NCLBUTTONDOWN, HT_CAPTION, 0);
            }
        }
        #endregion
        #region buttonEnterLogin enabled = true/false
        private void TextBoxPassword_TextChanged(object sender, EventArgs e)
        {
            TextBoxPassword.Text = Regex.Replace(TextBoxPassword.Text, "[^A-Za-z0-9]", "");
            ButtonEnterLogin.Enabled = TextBoxLogin.Text != "" && TextBoxPassword.Text != "";
        }

        private void TextBoxLogin_TextChanged(object sender, EventArgs e)
        {
            TextBoxLogin.Text = Regex.Replace(TextBoxLogin.Text, "[^A-Za-z0-9]", "");
            ButtonEnterLogin.Enabled = TextBoxLogin.Text != "" && TextBoxPassword.Text != "";
        }
        #endregion
        #region Вход
        [Obsolete]
        private async void ButtonEnterLogin_Click(object sender, EventArgs e)
        {
            DataTable table = new DataTable();
            SQLiteDataAdapter adapter = new SQLiteDataAdapter();
            SQLiteDataReader sqlReader = null;
            SQLiteCommand command = new SQLiteCommand($"SELECT * FROM [{Table_users.main}] WHERE [{Table_users.login}] = '" + TextBoxLogin.Text + $"' AND [{Table_users.pass}] = '" + TextBoxPassword.Text + "'", DB);
            try
            {
                adapter.SelectCommand = command;
                _ = adapter.Fill(table);
                if (table.Rows.Count > 0)
                {
                    sqlReader = (SQLiteDataReader)await command.ExecuteReaderAsync();
                    while (await sqlReader.ReadAsync())
                    {
                        string checkLocked = sqlReader[$"{Table_users.typeAccess}"].ToString();
                        if (checkLocked == "" || checkLocked == null)
                        {
                            DataUsers.Family = sqlReader[$"{Table_users.family}"].ToString();
                            DataUsers.Name = sqlReader[$"{Table_users.name}"].ToString();
                            DataUsers.Father = sqlReader[$"{Table_users.father}"].ToString();
                            DataUsers.Initials = sqlReader[$"{Table_users.initials}"].ToString();
                            DataUsers.Gender = sqlReader[$"{Table_users.gender}"].ToString();
                            DataUsers.Number = sqlReader[$"{Table_users.number}"].ToString();
                            DataUsers.Email = sqlReader[$"{Table_users.email}"].ToString();
                            DataUsers.Depart = sqlReader[$"{Table_users.depart}"].ToString();
                            DataUsers.Position = sqlReader[$"{Table_users.position}"].ToString();
                            DataUsers.Login = sqlReader[$"{Table_users.login}"].ToString();
                            DataUsers.Pass = sqlReader[$"{Table_users.pass}"].ToString();
                            DataUsers.GroupUser = sqlReader[$"{Table_users.groupUser}"].ToString();
                            DataUsers.Image = sqlReader[$"{Table_users.image}"].ToString();
                            if (sqlReader[$"{Table_users.groupUser}"].ToString() == "ADMIN")
                            {
                                Form fMain = new MainAdminForm();
                                fMain.Show();
                                fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                                Hide();
                            }
                            else if (sqlReader[$"{Table_users.groupUser}"].ToString() == "WORKER")
                            {
                                Form fMain = new MainWorkerForm();
                                fMain.Show();
                                fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                                Hide();
                            }
                            else if (sqlReader[$"{Table_users.groupUser}"].ToString() == "USER")
                            {
                                Form fMain = new MainUserForm();
                                fMain.Show();
                                fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                                Hide();
                            }
                            await NewModulesDb.AutoEnterOnLoginAsync();
                            File.AppendAllText(Logs.file, $"[Вход]{DataUsers.Initials} ({thisDay:dd.MM.yyyy HH:mm})");
                            File.AppendAllText(Logs.file, Environment.NewLine);
                            CheckValidatePassword();
                        }
                        else
                        {
                            MessageBoxUI.Show("Учетная запись заблокирована! Свяжитесь с системным администратором для восстановления.", "Ошибка авторизации", "Error");
                            Close();
                        }
                    }
                }
                else
                {
                    string login = TextBoxLogin.Text;
                    SQLiteCommand commandCheck = new SQLiteCommand($"SELECT * FROM [{Table_users.main}] WHERE [{Table_users.login}]=@login", DB);
                    _ = commandCheck.Parameters.AddWithValue("login", login);
                    sqlReader = (SQLiteDataReader)await commandCheck.ExecuteReaderAsync();
                    while (await sqlReader.ReadAsync())
                    {
                        string check = sqlReader[$"{Table_users.typeAccess}"].ToString();
                        if (attemptLogin > 0 && check != "LOCKED")
                        {
                            attemptLogin -= 1;
                            MessageBoxUI.Show("Неверный логин или пароль", "Ошибка авторизации", "Error");
                        }
                        else
                        {
                            string locked = "LOCKED";
                            SQLiteCommand commandUpdate = new SQLiteCommand($"UPDATE {Table_users.main} SET [{Table_users.typeAccess}]=@locked WHERE [{Table_users.login}] = @login", DB);
                            _ = commandUpdate.Parameters.AddWithValue("login", login);
                            _ = commandUpdate.Parameters.AddWithValue("locked", locked);
                            _ = await commandUpdate.ExecuteNonQueryAsync();
                            File.AppendAllText(Logs.file, $"[Вход]Учетная запись пользователя {login}|{sqlReader[$"{Table_users.initials}"]}| заблокирована!({thisDay:dd.MM.yyyy HH:mm})");
                            File.AppendAllText(Logs.file, Environment.NewLine);
                            MessageBoxUI.Show("Учетная запись заблокирована! Свяжитесь с системным администратором для восстановления.", "Ошибка авторизации", "Error");
                            Close();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBoxUI.Show($"{ex.Message}", $"{ex.Source}", "Error");
            }
            finally
            {
                sqlReader?.Close();
            }
        }

        [Obsolete]
        public async void EnterLoginPerUser(SQLiteConnection DB)
        {
            DataTable table = new DataTable();
            SQLiteDataAdapter adapter = new SQLiteDataAdapter();
            SQLiteDataReader sqlReader = null;
            SQLiteCommand command = new SQLiteCommand($"SELECT * FROM [{Table_users.main}] WHERE [{Table_users.login}] = '" + LoginPerUser.Login + $"' AND [{Table_users.pass}] = '" + LoginPerUser.Pass + "'", DB);
            try
            {
                adapter.SelectCommand = command;
                _ = adapter.Fill(table);
                if (table.Rows.Count > 0)
                {
                    sqlReader = (SQLiteDataReader)await command.ExecuteReaderAsync();
                    while (await sqlReader.ReadAsync())
                    {
                        DataUsers.Family = sqlReader[$"{Table_users.family}"].ToString();
                        DataUsers.Name = sqlReader[$"{Table_users.name}"].ToString();
                        DataUsers.Father = sqlReader[$"{Table_users.father}"].ToString();
                        DataUsers.Initials = sqlReader[$"{Table_users.initials}"].ToString();
                        DataUsers.Number = sqlReader[$"{Table_users.number}"].ToString();
                        DataUsers.Email = sqlReader[$"{Table_users.email}"].ToString();
                        DataUsers.Depart = sqlReader[$"{Table_users.depart}"].ToString();
                        DataUsers.Position = sqlReader[$"{Table_users.position}"].ToString();
                        DataUsers.Login = sqlReader[$"{Table_users.login}"].ToString();
                        DataUsers.Pass = sqlReader[$"{Table_users.pass}"].ToString();
                        DataUsers.GroupUser = sqlReader[$"{Table_users.groupUser}"].ToString();
                        DataUsers.Image = sqlReader[$"{Table_users.image}"].ToString();
                        if (sqlReader[$"{Table_users.groupUser}"].ToString() == "ADMIN")
                        {
                            Form fMain = new MainAdminForm();
                            fMain.Show();
                            fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                            Hide();
                        }
                        else if (sqlReader[$"{Table_users.groupUser}"].ToString() == "WORKER")
                        {
                            Form fMain = new MainWorkerForm();
                            fMain.Show();
                            fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                            Hide();
                        }
                        else if (sqlReader[$"{Table_users.groupUser}"].ToString() == "USER")
                        {
                            Form fMain = new MainUserForm();
                            fMain.Show();
                            fMain.FormClosed += new FormClosedEventHandler(Form_FormClosed);
                            Hide();
                        }
                        await NewModulesDb.AutoEnterOnLoginAsync();
                            File.AppendAllText(Logs.file, $"[Вход]{DataUsers.Initials} ({thisDay:dd.MM.yyyy HH:mm})");
                        File.AppendAllText(Logs.file, Environment.NewLine);
                        CheckValidatePassword();
                    }
                }
                else
                {
                    MessageBoxUI.Show("Неверный логин или пароль", "Ошибка авторизации", "Error");
                }
            }
            catch (Exception ex)
            {
                MessageBoxUI.Show($"{ex.Message}", $"{ex.Source}", "Error");
            }
            finally
            {
                sqlReader?.Close();
            }
        }
        #endregion
    }
}