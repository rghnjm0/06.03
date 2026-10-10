using System;
using System.Collections.Generic;
using System.Data.SQLite;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SupportDesk.forms
{
    internal static class Table_serverAccess
    {
        public static string main = "ServerRoomVisits";
        public static string visitor = "visitor";
        public static string enterDate = "enterDate";
        public static string enterTime = "enterTime";
        public static string exitTime = "exitTime";
        public static string note = "note";
    }

    /// <summary>
    /// Журнал: запись при входе в программу, время выхода при logout.
    /// </summary>
    public static class NewModulesDb
    {
        private static long _openRowId = -1;
        private static string _openVisitor;
        public static string LastError { get; private set; }

        public static async Task EnsureAsync(SQLiteConnection db)
        {
            if (db == null) throw new Exception("Нет подключения к БД");

            using (SQLiteCommand command = new SQLiteCommand(@"
CREATE TABLE IF NOT EXISTS ServerRoomVisits (
    ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    visitor TEXT NOT NULL,
    enterDate TEXT NOT NULL,
    enterTime TEXT NOT NULL,
    exitTime TEXT,
    note TEXT
);", db))
            {
                await command.ExecuteNonQueryAsync();
            }
        }

        private static async Task<string> BuildWorkNoteAsync(string visitor)
        {
            // USER — «что делал» не нужно, только факт входа/выхода
            if (string.Equals(DataUsers.GroupUser, "USER", StringComparison.OrdinalIgnoreCase))
                return "";

            if (string.IsNullOrWhiteSpace(visitor)) visitor = DataUsers.Initials ?? "";
            var lines = new List<string>();
            try
            {
                using (SQLiteConnection db = new SQLiteConnection(Database.connectionString))
                {
                    await db.OpenAsync();
                    using (SQLiteCommand cmd = new SQLiteCommand(@"
SELECT tema, typeProblem, status, kabinet
FROM Requests
WHERE (executor = @v OR executor2 = @v)
  AND (status = 'В работе' OR status = 'Новая' OR status = 'На подтверждении')
ORDER BY ID DESC LIMIT 5", db))
                    {
                        cmd.Parameters.AddWithValue("v", visitor);
                        using (SQLiteDataReader r = (SQLiteDataReader)await cmd.ExecuteReaderAsync())
                        {
                            while (await r.ReadAsync())
                            {
                                lines.Add(string.Format("{0}: [{1}] {2} (каб. {3})",
                                    r["status"], r["typeProblem"], r["tema"], r["kabinet"]));
                            }
                        }
                    }
                }
            }
            catch
            {
                return "";
            }
            if (lines.Count == 0) return "";
            string note = string.Join("; ", lines.ToArray());
            if (note.Length > 400) note = note.Substring(0, 400) + "…";
            return note;
        }

        /// <summary>Вход в программу (MainAdminForm_Load / MainWorkerForm_Load).</summary>
        public static async Task AutoEnterOnLoginAsync()
        {
            LastError = null;
            try
            {
                string who = (DataUsers.Initials ?? "").Trim();
                if (string.IsNullOrWhiteSpace(who))
                {
                    who = string.Format("{0} {1} {2}",
                        DataUsers.Family ?? "",
                        DataUsers.Name ?? "",
                        DataUsers.Father ?? "").Trim();
                }
                if (string.IsNullOrWhiteSpace(who))
                    who = (DataUsers.Login ?? "").Trim();
                if (string.IsNullOrWhiteSpace(who)) who = "Неизвестно";

                if (_openRowId > 0 && _openVisitor == who) return;

                string note = await BuildWorkNoteAsync(who);
                DateTime now = DateTime.Now;

                using (SQLiteConnection db = new SQLiteConnection(Database.connectionString))
                {
                    await db.OpenAsync();
                    await EnsureAsync(db);

                    // закрыть незакрытые сессии этого пользователя
                    using (SQLiteCommand fix = new SQLiteCommand(
                        "UPDATE ServerRoomVisits SET exitTime=@t WHERE visitor=@v AND (exitTime IS NULL OR exitTime='')", db))
                    {
                        fix.Parameters.AddWithValue("t", now.ToString("HH:mm:ss"));
                        fix.Parameters.AddWithValue("v", who);
                        await fix.ExecuteNonQueryAsync();
                    }

                    using (SQLiteCommand command = new SQLiteCommand(
                        "INSERT INTO ServerRoomVisits (visitor, enterDate, enterTime, exitTime, note) VALUES (@v, @ed, @et, '', @n)", db))
                    {
                        command.Parameters.AddWithValue("v", who);
                        command.Parameters.AddWithValue("ed", now.ToString("dd.MM.yyyy"));
                        command.Parameters.AddWithValue("et", now.ToString("HH:mm:ss"));
                        command.Parameters.AddWithValue("n", note ?? "");
                        int n = await command.ExecuteNonQueryAsync();
                        if (n < 1) throw new Exception("INSERT не добавил строку");
                    }

                    using (SQLiteCommand idCmd = new SQLiteCommand("SELECT last_insert_rowid()", db))
                    {
                        _openRowId = Convert.ToInt64(await idCmd.ExecuteScalarAsync());
                        _openVisitor = who;
                    }
                }

                try
                {
                    File.AppendAllText(Logs.file,
                        string.Format("[Журнал]Вход {0} {1:dd.MM.yyyy HH:mm:ss} | {2}{3}", who, now, note, Environment.NewLine));
                }
                catch { }
            }
            catch (Exception ex)
            {
                LastError = ex.Message;
                try { MessageBox.Show("Журнал (вход): " + ex.Message, "Ошибка журнала"); } catch { }
            }
        }

        /// <summary>Выход из программы (кнопка logout).</summary>
        public static async Task AutoExitOnLogoutAsync()
        {
            LastError = null;
            try
            {
                string who = DataUsers.Initials ?? _openVisitor ?? "Неизвестно";
                if (string.IsNullOrWhiteSpace(who)) who = "Неизвестно";
                string note = await BuildWorkNoteAsync(who);
                string exitT = DateTime.Now.ToString("HH:mm:ss");

                using (SQLiteConnection db = new SQLiteConnection(Database.connectionString))
                {
                    await db.OpenAsync();
                    await EnsureAsync(db);

                    int updated = 0;
                    if (_openRowId > 0)
                    {
                        using (SQLiteCommand command = new SQLiteCommand(
                            "UPDATE ServerRoomVisits SET exitTime=@t, note=@n WHERE ID=@id", db))
                        {
                            command.Parameters.AddWithValue("t", exitT);
                            command.Parameters.AddWithValue("n", note ?? "");
                            command.Parameters.AddWithValue("id", _openRowId);
                            updated = await command.ExecuteNonQueryAsync();
                        }
                    }

                    if (updated == 0)
                    {
                        using (SQLiteCommand command = new SQLiteCommand(
                            "UPDATE ServerRoomVisits SET exitTime=@t, note=@n WHERE ID = (SELECT MAX(ID) FROM ServerRoomVisits WHERE visitor=@v AND (exitTime IS NULL OR exitTime=''))", db))
                        {
                            command.Parameters.AddWithValue("t", exitT);
                            command.Parameters.AddWithValue("n", note ?? "");
                            command.Parameters.AddWithValue("v", who);
                            await command.ExecuteNonQueryAsync();
                        }
                    }
                }

                _openRowId = -1;
                _openVisitor = null;
                try
                {
                    File.AppendAllText(Logs.file,
                        string.Format("[Журнал]Выход {0} {1} | {2}{3}", who, exitT, note, Environment.NewLine));
                }
                catch { }
            }
            catch (Exception ex)
            {
                LastError = ex.Message;
                try { MessageBox.Show("Журнал (выход): " + ex.Message, "Ошибка журнала"); } catch { }
            }
        }
    }
}
