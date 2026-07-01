local RESOURCE = GetCurrentResourceName()
local lastPed = 0
local applyCount = 0

local function debugPrint(message)
    if Config.Debug then
        print(('[%s] %s'):format(RESOURCE, message))
    end
end

local function enableCriticalHits(reason)
    local ped = PlayerPedId()
    if ped == 0 or not DoesEntityExist(ped) then
        return false
    end

    SetPedSuffersCriticalHits(ped, true)
    lastPed = ped

    if Config.Debug then
        applyCount = applyCount + 1
        debugPrint(('critical hits ON | reason=%s | ped=%s | count=%s'):format(reason or 'unknown', ped, applyCount))
    end

    return true
end

local function delayedApply(reason)
    CreateThread(function()
        Wait(0)
        enableCriticalHits(reason)
        Wait(250)
        enableCriticalHits(reason .. ':delayed')
    end)
end

AddEventHandler('onClientResourceStart', function(resourceName)
    if resourceName == RESOURCE then
        delayedApply('resource_start')
    end
end)

AddEventHandler('playerSpawned', function()
    delayedApply('playerSpawned')
end)

RegisterNetEvent('esx:playerLoaded', function()
    delayedApply('esx:playerLoaded')
end)

RegisterNetEvent('esx:onPlayerSpawn', function()
    delayedApply('esx:onPlayerSpawn')
end)

RegisterNetEvent('QBCore:Client:OnPlayerLoaded', function()
    delayedApply('QBCore:Client:OnPlayerLoaded')
end)

RegisterNetEvent('qbx_core:client:playerLoggedIn', function()
    delayedApply('qbx_core:client:playerLoggedIn')
end)

RegisterNetEvent('skinchanger:modelLoaded', function()
    delayedApply('skinchanger:modelLoaded')
end)

RegisterNetEvent('illenium-appearance:client:reloadSkin', function()
    delayedApply('illenium-appearance:reloadSkin')
end)

CreateThread(function()
    while true do
        local mode = tostring(Config.Mode or 'strict'):lower()

        if mode == 'strict' then
            Wait(0)
            local ped = PlayerPedId()
            if ped ~= 0 then
                -- Ruta caliente deliberadamente mínima: una sola native de estado.
                SetPedSuffersCriticalHits(ped, true)
                if ped ~= lastPed then
                    lastPed = ped
                    debugPrint(('critical hits ON | ped_changed=%s'):format(ped))
                end
            end
        elseif mode == 'safe' then
            Wait(math.max(50, tonumber(Config.Interval) or 250))
            enableCriticalHits('safe')
        else
            Wait(500)
            local ped = PlayerPedId()
            if ped ~= 0 and ped ~= lastPed then
                enableCriticalHits('ped_changed')
            end
        end
    end
end)

RegisterCommand(Config.DebugCommand or 'osheadshotstatus', function()
    local ped = PlayerPedId()
    print(('[%s] mode=%s ped=%s health=%s armour=%s debugApplyCount=%s'):format(
        RESOURCE,
        tostring(Config.Mode),
        ped,
        GetEntityHealth(ped),
        GetPedArmour(ped),
        applyCount
    ))
end, false)

exports('ReapplyCriticalHits', function(reason)
    return enableCriticalHits(reason or 'export')
end)
