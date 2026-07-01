Config = {}

-- event: solo al iniciar/cambiar ped/eventos conocidos.
-- safe:  reafirma cada Interval ms.
-- strict: reafirma cada frame. Es la opción necesaria si otro recurso usa Wait(0) con false.
Config.Mode = 'strict'
Config.Interval = 250
Config.Debug = false

-- Comando local para mostrar el estado administrado por este recurso.
Config.DebugCommand = 'osheadshotstatus'
