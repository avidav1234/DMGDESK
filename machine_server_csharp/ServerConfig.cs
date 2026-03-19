using System;
using System.IO;
using System.Text;

namespace MachineServer
{
    /// <summary>
    /// Legge e scrive la configurazione da server_config.ini
    /// Compatibile con .NET 2.0 / Windows XP
    /// </summary>
    public class ServerConfig
    {
        private static readonly string ConfigPath =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "server_config.ini");

        public int    Port     = 9999;
        public string BasePath = @"F:\dh\wks.dir";
        public string DncPath  = @"D:\tmp\autoimport";
        public string VbsPath  = @"F:\ADD_ON\DNC\transfer_dnc.vbs";

        public static ServerConfig Load()
        {
            ServerConfig cfg = new ServerConfig();

            if (!File.Exists(ConfigPath))
            {
                cfg.Save();   // crea il file con i default
                return cfg;
            }

            try
            {
                foreach (string line in File.ReadAllLines(ConfigPath, Encoding.UTF8))
                {
                    string l = line.Trim();
                    if (l.StartsWith(";") || l.StartsWith("[") || !l.Contains("="))
                        continue;

                    int eq   = l.IndexOf('=');
                    string k = l.Substring(0, eq).Trim().ToLower();
                    string v = l.Substring(eq + 1).Trim();

                    if (k == "port")
                    {
                        int p;
                        if (int.TryParse(v, out p)) cfg.Port = p;
                    }
                    else if (k == "base_path")
                    {
                        cfg.BasePath = v;
                    }
                    else if (k == "dnc_path")
                    {
                        cfg.DncPath = v;
                    }
                    else if (k == "vbs_path")
                    {
                        cfg.VbsPath = v;
                    }
                }
            }
            catch { /* usa i default */ }

            return cfg;
        }

        public void Save()
        {
            try
            {
                string[] lines = new string[]
                {
                    "[server]",
                    "port=" + Port,
                    "base_path=" + BasePath,
                    "dnc_path="  + DncPath,
                    "vbs_path="  + VbsPath
                };
                File.WriteAllLines(ConfigPath, lines, Encoding.UTF8);
            }
            catch { }
        }
    }
}


